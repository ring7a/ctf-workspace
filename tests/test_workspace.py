"""Portable asset integration tests; no model calls or upstream download."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "tools/check-workspace.py"
SKILLS = ("ctf-ai-ml", "ctf-crypto", "ctf-forensics", "ctf-malware", "ctf-misc",
          "ctf-osint", "ctf-pwn", "ctf-reverse", "ctf-web", "ctf-writeup", "solve-challenge")


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ctf-workspace-check-")
        self.root = Path(self.temp.name).resolve() / "fixture"
        self.root.mkdir()
        for skill in SKILLS:
            self.write(f".claude/skills/{skill}/SKILL.md", f"---\nname: {skill}\ndescription: Fixture skill\n---\n# Example\n")
        for role in ("solver", "triager", "verifier"):
            self.write(f".codex/agents/{role}.toml", f'name = "{role}"\ndescription = "Fixture role"\ndeveloper_instructions = "Fixture instructions"\n')
            self.write(f".claude/agents/{role}.md", f"# {role}\n")
        for rel in ("CLAUDE.md", "AGENTS.md", "docs/SKILL-INTEGRATION.md", "docs/PRE-CTF-INTAKE.md", "events/_TEMPLATE/NOTES.md"):
            self.write(rel, "# Fixture\n")
        self.write("tools/vendor-ctf-skills/PINNED_COMMIT.txt", "a" * 40 + "\n")
        self.write("tools/vendor-ctf-skills/LICENSE", "Fixture notice\n")
        self.write("tools/check-workspace.py", CHECK.read_text(encoding="utf-8"))
        self.write("setup.ps1", (ROOT / "setup.ps1").read_text(encoding="utf-8"))
        self.assertEqual(self.run_check("--sync").returncode, 0)

    def tearDown(self):
        # Only the directory allocated by TemporaryDirectory is removed.
        self.assertTrue(self.root.is_relative_to(Path(self.temp.name).resolve()))
        self.temp.cleanup()

    def write(self, rel, content):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        return path

    def run_check(self, *extra):
        return subprocess.run([sys.executable, "-I", str(CHECK), "--root", str(self.root), *extra], capture_output=True, text=True)

    def test_fresh_export_and_idempotent_sync(self):
        before = (self.root / "tools/workspace-manifest.json").read_bytes()
        self.assertNotIn(b"\r", before)
        self.assertEqual(self.run_check().returncode, 0)
        self.assertEqual(self.run_check("--sync").returncode, 0)
        self.assertEqual(before, (self.root / "tools/workspace-manifest.json").read_bytes())

    def test_canonical_change_updates_unchanged_mirror(self):
        path = self.root / ".claude/skills/ctf-misc/SKILL.md"
        path.write_bytes(path.read_bytes() + b"\nCanonical update\n")
        self.assertNotEqual(self.run_check().returncode, 0)
        self.assertEqual(self.run_check("--sync").returncode, 0)
        self.assertEqual(path.read_bytes(), (self.root / ".agents/skills/ctf-misc/SKILL.md").read_bytes())

    def test_mirror_local_edit_preserved_before_any_write(self):
        edited = self.root / ".agents/skills/ctf-misc/SKILL.md"
        edited.write_bytes(edited.read_bytes() + b"\nStudent change\n")
        original = edited.read_bytes()
        source = self.root / ".claude/skills/ctf-web/SKILL.md"
        source.write_bytes(source.read_bytes() + b"\nOther update\n")
        old_other = (self.root / ".agents/skills/ctf-web/SKILL.md").read_bytes()
        result = self.run_check("--sync")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Local mirror edit preserved", result.stderr)
        self.assertEqual(original, edited.read_bytes())
        self.assertEqual(old_other, (self.root / ".agents/skills/ctf-web/SKILL.md").read_bytes())

    def test_missing_mirror_restored(self):
        path = self.root / ".agents/skills/ctf-pwn/SKILL.md"
        path.unlink()
        self.assertNotEqual(self.run_check().returncode, 0)
        self.assertEqual(self.run_check("--sync").returncode, 0)
        self.assertTrue(path.is_file())

    def test_extra_mirror_file_preserved(self):
        path = self.write(".agents/skills/custom/SKILL.md", "student-owned\n")
        self.assertNotEqual(self.run_check("--sync").returncode, 0)
        self.assertEqual(path.read_text(), "student-owned\n")

    def test_broken_local_link_rejected(self):
        path = self.root / ".claude/skills/ctf-web/SKILL.md"
        path.write_bytes(path.read_bytes() + b"\n[Missing](gone.md)\n")
        result = self.run_check("--sync")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Broken link", result.stderr)

    def test_code_is_not_a_markdown_link(self):
        path = self.root / ".claude/skills/ctf-web/SKILL.md"
        path.write_bytes(path.read_bytes() + b"\n`x['y']('z')`\n```python\nx['y']('z')\n```\n")
        self.assertEqual(self.run_check("--sync").returncode, 0)

    def test_role_schema_rejected(self):
        self.write(".codex/agents/solver.toml", 'name = "solver"\n')
        self.assertNotEqual(self.run_check().returncode, 0)

    def test_symlink_escape_rejected_without_touching_destination(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        try:
            (self.root / ".agents/skills/escape").symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Symlink permission unavailable: {error}")
        self.assertNotEqual(self.run_check("--sync").returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell"), "Windows PowerShell test")
    def test_setup_stops_on_native_git_failure(self):
        fake_bin = Path(self.temp.name) / "fake-bin"
        fake_bin.mkdir()
        (fake_bin / "git.cmd").write_bytes(b"@echo off\r\nexit /b 37\r\n")
        environment = dict(os.environ, PATH=str(fake_bin) + os.pathsep + os.environ["PATH"])
        before = (self.root / "tools/workspace-manifest.json").read_bytes()
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.root / "setup.ps1"), "-FetchUpstream"], env=environment, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exit code 37", result.stderr)
        self.assertEqual(before, (self.root / "tools/workspace-manifest.json").read_bytes())
        self.assertNotIn("Verified", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
