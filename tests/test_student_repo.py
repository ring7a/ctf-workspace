"""Allowlist-export regression tests. No Git, network, model or challenge execution."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("student_export", ROOT / "tools/build-student-repo.py")
EXPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORTER)


class StudentRepoTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ctf-student-export-")
        self.root = Path(self.temporary.name) / "fixture"
        self.root.mkdir()
        for relative in EXPORTER.EXACT_FILES:
            self.write(relative, "# Fixture\n")
        for directory in EXPORTER.TREE_FILES:
            self.write(directory + "/fixture.md", "# Fixture\n")
        self.write("AGENTS.md", "# Agent\n\n## 환경\nold environment\n\n## 보고 형식\nreport\n")
        self.write("CLAUDE.md", "# Claude\n\n## 환경\nold environment\n\n## 보고 형식\nreport\n")
        self.write("docs/STUDENT-GUIDE.md", "# Student\n\n## 10. 벤치마크 수업\nold design\n\n## 11. 실습 완료 기준\nfinish\n")
        self.write("tools/workspace-manifest.json", '{"schema_version":1,"skill_sha256":{}}\n')
        self.write("tools/check-workspace.py", (ROOT / "tools/check-workspace.py").read_text(encoding="utf-8"))
        self.write(".gitattributes", (ROOT / ".gitattributes").read_text(encoding="utf-8"))
        self.write(".claude/skills/example/SKILL.md", "---\nname: example\ndescription: Fixture\n---\n")
        self.write(".agents/skills/example/SKILL.md", "---\nname: example\ndescription: Fixture\n---\n")
        self.destination = self.root / "dist/student-repo"

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    def test_actual_working_assets_pass_plan_and_dependency_closure(self):
        files, manifest = EXPORTER.plan_export(ROOT)
        for dependency in ("tools/check-workspace.py", "tools/workspace-manifest.json",
                           "tools/vendor-ctf-skills/scripts/install_ctf_tools.sh",
                           "tools/wsl/ctf-venv-requirements.txt"):
            self.assertIn(dependency, files)
        self.assertEqual(len(files), manifest["file_count_excluding_manifest"] + 1)
        self.assertNotIn(".claude/settings.json", files)
        self.assertTrue(all(not path.startswith(("benchmarks/", ".git/")) for path in files))
        self.assertTrue(all(not Path(path).suffix.lower() in (".ppt", ".pptx", ".pot", ".potx", ".pdf") for path in files))

    def test_export_includes_rea_and_excludes_retired_ctf_agent(self):
        retired = ("tools/ctf-agent.sh", "tools/integrations/install-ctf-agent.sh",
                   "tools/integrations/ctf_agent_adapter.py", "tools/integrations/authenticated_models.py",
                   "tests/test_ctf_agent_integration.py", "tests/test_authenticated_models.py")
        for relative in retired:
            self.write(relative, "retired adapter must stay local\n")
        files, _ = EXPORTER.plan_export(self.root)
        self.assertIn("tools/rea.sh", files)
        self.assertIn("tools/integrations/install-rea.sh", files)
        self.assertTrue(all(relative not in files for relative in retired))
        self.assertNotIn("ctf-agent", files["README.md"].decode("utf-8"))
        actual, _ = EXPORTER.plan_export(ROOT)
        self.assertTrue(all("ctf-agent" not in relative and "authenticated_models" not in relative
                            for relative in actual))
        self.assertNotIn("ctf_agent", json.loads(actual["tools/integrations/reviewed-versions.json"]))

    def test_export_manifest_commits_source_and_output_bytes(self):
        result = EXPORTER.export(self.root, self.destination)
        manifest = json.loads((self.destination / EXPORTER.MANIFEST_NAME).read_text(encoding="utf-8"))
        for entry in manifest["files"]:
            source = (self.root / entry["source_path"]).read_bytes()
            output = (self.destination / entry["output_path"]).read_bytes()
            self.assertEqual(hashlib.sha256(source).hexdigest(), entry["source_sha256"])
            self.assertEqual(hashlib.sha256(output).hexdigest(), entry["output_sha256"])
        self.assertEqual(result["files"], len(manifest["files"]) + 1)
        self.assertFalse((self.destination / ".git").exists())

    def test_exports_are_deterministic_and_do_not_change_source(self):
        before = {relative: (self.root / relative).read_bytes() for relative in EXPORTER.selected_files(self.root)}
        first = EXPORTER.export(self.root, self.destination)
        second_root = self.root / "dist/second"
        second = EXPORTER.export(self.root, second_root)
        self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])
        for relative, content in before.items():
            self.assertEqual((self.root / relative).read_bytes(), content)
            self.assertEqual((self.destination / relative).read_bytes(), (second_root / relative).read_bytes())

    def test_skill_manifest_preserves_reviewed_key_order(self):
        order = {"fixture.md": "old", "example/SKILL.md": "old"}
        self.write("tools/workspace-manifest.json", json.dumps({"schema_version": 1, "skill_sha256": order}))
        files, _ = EXPORTER.plan_export(self.root)
        actual = json.loads(files["tools/workspace-manifest.json"])["skill_sha256"]
        self.assertEqual(list(actual), list(order))
        self.assertTrue(all(value != "old" for value in actual.values()))

    def test_portable_manifest_writer_normalization_is_idempotent(self):
        source = (ROOT / "tools/check-workspace.py").read_text(encoding="utf-8")
        normalized, _ = EXPORTER.normalize("tools/check-workspace.py", source)
        again, changes = EXPORTER.normalize("tools/check-workspace.py", normalized)
        self.assertEqual(normalized, again)
        self.assertEqual(changes, [])

    @unittest.skipUnless(shutil.which("git"), "Git is required for checkout-byte regression")
    def test_git_checkout_with_autocrlf_preserves_manifest_bytes(self):
        EXPORTER.export(self.root, self.destination)
        def git(*arguments, cwd=None):
            result = subprocess.run(["git", *arguments], cwd=cwd, text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
        git("init", "--quiet", str(self.destination))
        git("-c", "core.autocrlf=true", "add", ".", cwd=self.destination)
        git("-c", "user.name=Student Export Test", "-c", "user.email=student-export-test@example.invalid",
            "commit", "--quiet", "-m", "Fixture export", cwd=self.destination)
        checkout = self.root.parent / "checkout"
        git("-c", "core.autocrlf=true", "clone", "--no-hardlinks", "--quiet", str(self.destination), str(checkout))
        manifest = json.loads((checkout / EXPORTER.MANIFEST_NAME).read_text(encoding="utf-8"))
        for entry in manifest["files"]:
            with self.subTest(path=entry["output_path"]):
                data = (checkout / entry["output_path"]).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), entry["output_sha256"])
                self.assertNotIn(b"\r", data)
        self.assertEqual((self.destination / EXPORTER.MANIFEST_NAME).read_bytes(),
                         (checkout / EXPORTER.MANIFEST_NAME).read_bytes())

    def test_nonempty_destination_is_preserved(self):
        self.destination.mkdir(parents=True)
        sentinel = self.destination / "keep.txt"
        sentinel.write_text("precious")
        with self.assertRaisesRegex(ValueError, "empty directory"):
            EXPORTER.export(self.root, self.destination)
        self.assertEqual(sentinel.read_text(), "precious")
        self.assertEqual(list(self.destination.iterdir()), [sentinel])

    def test_destination_outside_dist_is_refused(self):
        for destination in (self.root, self.root / "dist", self.root.parent / "outside"):
            with self.subTest(destination=destination):
                with self.assertRaisesRegex(ValueError, "child.*dist"):
                    EXPORTER.export(self.root, destination)
        self.assertFalse((self.root.parent / "outside").exists())

    def test_unallowed_asset_type_stops_before_writes(self):
        self.write(".claude/skills/example/lecture.pptx", "not even a real deck")
        with self.assertRaisesRegex(ValueError, "Unallowed file type"):
            EXPORTER.export(self.root, self.destination)
        self.assertFalse(self.destination.exists())

    def test_secret_in_replaced_readme_cannot_be_hidden_by_normalization(self):
        candidate = "ghp_" + "A" * 36
        self.write("README.md", candidate)
        with self.assertRaises(ValueError) as caught:
            EXPORTER.export(self.root, self.destination)
        self.assertIn("Possible GitHub token", str(caught.exception))
        self.assertNotIn(candidate, str(caught.exception))
        self.assertFalse(self.destination.exists())

    def test_unexpected_personal_path_stops_before_writes(self):
        self.write("docs/PRE-CTF-INTAKE.md", "Copy E:/_/Orca/private/data\n")
        with self.assertRaisesRegex(ValueError, "Personal path"):
            EXPORTER.export(self.root, self.destination)
        self.assertFalse(self.destination.exists())

    def test_original_git_and_event_and_deck_data_are_not_selected(self):
        for relative in (".git/objects/secret", "events/private/NOTES.md", "docs/slides.pptx",
                         "benchmarks/runs/.private/seed.bin", ".claude/settings.json",
                         ".integrations/rea/install-state.json", ".mcp.json", ".codex/config.toml"):
            self.write(relative, "never copy me")
        files, _ = EXPORTER.plan_export(self.root)
        self.assertTrue(all(b"never copy me" not in data for data in files.values()))
        for generated in (".integrations/", ".mcp.json", ".codex/config.toml"):
            self.assertIn(generated, files[".gitignore"].decode("utf-8").splitlines())

    def test_mirror_conflict_is_refused(self):
        self.write(".agents/skills/example/SKILL.md", "student local edit\n")
        with self.assertRaisesRegex(ValueError, "Canonical/mirror mismatch"):
            EXPORTER.export(self.root, self.destination)
        self.assertFalse(self.destination.exists())

    def test_broken_link_stops_before_writes(self):
        self.write("docs/PRE-CTF-INTAKE.md", "[Missing](missing.md)\n")
        with self.assertRaisesRegex(ValueError, "Broken exported Markdown link"):
            EXPORTER.export(self.root, self.destination)
        self.assertFalse(self.destination.exists())

    def test_symlink_source_is_refused(self):
        selected = self.root / "docs/PRE-CTF-INTAKE.md"
        outside = self.root.parent / "outside.md"
        outside.write_text("outside")
        selected.unlink()
        try:
            selected.symlink_to(outside)
        except OSError as error:
            self.skipTest(f"Symlink unavailable: {error}")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            EXPORTER.export(self.root, self.destination)
        self.assertFalse(self.destination.exists())

    def test_symlink_destination_parent_is_refused(self):
        outside = self.root.parent / "outside"
        outside.mkdir()
        try:
            (self.root / "dist").symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Symlink unavailable: {error}")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            EXPORTER.export(self.root, self.destination)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
