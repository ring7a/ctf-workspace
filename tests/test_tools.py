"""Local-only regression tests; run in WSL with python -I tests/test_tools.py."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ctf-tools-test-")
        self.base = Path(self.tmp.name)
        self.repo = self.base / "student's repo"
        (self.repo / "tools").mkdir(parents=True)
        for name in ("new-challenge.sh", "codex-crosscheck.sh"):
            shutil.copyfile(SOURCE / "tools" / name, self.repo / "tools" / name)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.env = {**os.environ, "PATH": f"{self.bin}:/usr/bin:/bin"}

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, name, *args):
        return subprocess.run(
            ["/bin/bash", str(self.repo / "tools" / name), *args],
            cwd=self.base, env=self.env, text=True, capture_output=True, timeout=10,
        )

    def fake(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/bash\n" + body, encoding="utf-8")
        path.chmod(0o755)

    def fake_codex(self, name="codex"):
        self.fake(name, 'printf "%s\\n" "$PWD" "$@"\n')

    def test_create_uses_repo_and_preserves_evidence_on_repeat(self):
        result = self.run_tool("new-challenge.sh", "test-event", "web-1")
        self.assertEqual(result.returncode, 0, result.stderr)
        target = self.repo / "events/test-event/challenges/web-1"
        self.assertTrue((target / "work").is_dir())
        self.assertTrue((target / "untrusted").is_dir())
        (target / "NOTES.md").write_text("precious evidence\n")
        result = self.run_tool("new-challenge.sh", "test-event", "web-1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((target / "NOTES.md").read_text(), "precious evidence\n")
        self.assertFalse((self.base / "events").exists())

    def test_path_traversal_and_bad_arity_rejected_without_creating_events(self):
        for args in (("../escape", "x"), ("event", "../../escape"),
                     ("event", "/tmp/escape"), ("event", ".."),
                     ("event", "x", "extra"), ("event", "")):
            with self.subTest(args=args):
                self.assertNotEqual(self.run_tool("new-challenge.sh", *args).returncode, 0)
        self.assertFalse((self.repo / "events").exists())

    def test_existing_and_dangling_parent_symlinks_rejected(self):
        outside = self.base / "outside"
        outside.mkdir()
        for component in ("events", "events/event", "events/event/challenges"):
            for destination in (outside, self.base / "missing"):
                with self.subTest(component=component, destination=destination):
                    link = self.repo / component
                    link.parent.mkdir(parents=True, exist_ok=True)
                    link.symlink_to(destination, target_is_directory=True)
                    result = self.run_tool("new-challenge.sh", "event", "one")
                    self.assertNotEqual(result.returncode, 0)
                    link.unlink()
        self.assertEqual(list(outside.iterdir()), [])

    def test_challenge_symlink_rejected(self):
        target = self.repo / "events/event/challenges/one"
        target.parent.mkdir(parents=True)
        target.symlink_to(self.base / "missing", target_is_directory=True)
        self.assertNotEqual(self.run_tool("new-challenge.sh", "event", "one").returncode, 0)
        self.assertFalse((self.base / "missing").exists())

    def test_question_is_one_literal_argument_with_separator(self):
        self.fake_codex()
        question = "--dangerously-bypass-approvals-and-sandbox; $(touch NOPE)"
        result = self.run_tool("codex-crosscheck.sh", question)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(self.repo), "exec", "--sandbox",
            "read-only", "--cd", str(self.repo), "--", question])
        self.assertFalse((self.repo / "NOPE").exists())

    def test_review_has_supported_argument_combination(self):
        self.fake_codex()
        result = self.run_tool("codex-crosscheck.sh", "--review")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(self.repo), "exec", "--sandbox",
            "read-only", "--cd", str(self.repo), "review", "--uncommitted"])

    def test_focused_review_uses_read_only_exec(self):
        self.fake_codex()
        result = self.run_tool("codex-crosscheck.sh", "--review", "WSL path quoting")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = result.stdout.splitlines()
        self.assertNotIn("--uncommitted", args)
        self.assertIn("read-only", args)
        self.assertIn("staged, unstaged, and untracked", args[-1])
        self.assertTrue(args[-1].endswith("WSL path quoting"))

    def test_windows_exe_receives_converted_root(self):
        self.fake_codex("codex.exe")
        self.fake("wslpath", "printf '%s\\n' 'D:\\student repo'\n")
        result = self.run_tool("codex-crosscheck.sh", "hypothesis")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[5], "D:\\student repo")

    def test_no_args_fails_before_cli_discovery(self):
        result = self.run_tool("codex-crosscheck.sh")
        self.assertEqual(result.returncode, 2)

    def test_provision_health_check_fails_if_any_import_fails(self):
        source = (SOURCE / "tools/wsl/provision-ubuntu-ctf.sh").read_text()
        health = source.split('echo "== provision: python tool check =="', 1)[1].split("\nUSERPART", 1)[0]
        venv = self.base / "venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "bin/activate").write_text(":\n")
        self.fake("python", '[[ "$1" == -I ]] || exit 90\n[[ "$3" != "import angr" ]]\n')
        result = subprocess.run(["/bin/bash", "-c", health],
            env={**self.env, "VENV": str(venv)}, text=True, capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL angr", result.stderr)
        self.assertIn("OK capstone", result.stdout)

    def test_provision_health_check_accepts_all_successful_imports(self):
        source = (SOURCE / "tools/wsl/provision-ubuntu-ctf.sh").read_text()
        health = source.split('echo "== provision: python tool check =="', 1)[1].split("\nUSERPART", 1)[0]
        venv = self.base / "venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "bin/activate").write_text(":\n")
        self.fake("python", '[[ "$1" == -I ]]\n')
        result = subprocess.run(["/bin/bash", "-c", health],
            env={**self.env, "VENV": str(venv)}, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("OK "), 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
