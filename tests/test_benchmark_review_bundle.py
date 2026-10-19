"""Inert exporter fixtures only: no model, submitted code or benchmark input runs.

Run in WSL: python -I tests/test_benchmark_review_bundle.py
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).absolute().parents[1]
SPEC = importlib.util.spec_from_file_location("benchmark_review_exporter", ROOT / "tools/prepare-benchmark-review.py")
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)
FLAG = "BENCH{" + "a" * 32 + "}"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def fixture(root):
    root.mkdir()
    (root / "active").mkdir()
    (root / ".incoming").mkdir()
    (root / ".private").mkdir()
    (root / ".private/master-seed.bin").write_bytes(b"excluded inert seed")
    (root / "answer-key.json").write_text("excluded inert key", encoding="utf-8")
    specs = []
    for arm in sorted(exporter.ARMS):
        instance = "lcg_stream-r1"
        identifier = arm + "-" + instance
        spec = {"id": identifier, "arm": arm, "instance": instance, "task": "lcg_stream", "repeat": 1,
                "provider": "claude+codex" if arm == "project_harness" else arm.removesuffix("_raw"),
                "condition": "harness" if arm == "project_harness" else "raw"}
        specs.append(spec)
        archive = root / "trials" / identifier
        challenge = archive / "events/local-benchmark/challenges" / instance
        (challenge / "work").mkdir(parents=True)
        (challenge / "untrusted").mkdir()
        (challenge / "untrusted/input.json").write_text("EXCLUDED_INPUT_CONTENT", encoding="utf-8")
        (archive / ".git").mkdir()
        (archive / ".git/config").write_text("EXCLUDED_GIT_CONTENT", encoding="utf-8")
        (archive / ".claude/skills").mkdir(parents=True)
        (archive / ".claude/skills/hidden.md").write_text("EXCLUDED_HARNESS_CONTENT", encoding="utf-8")
        (challenge / "work/solve.py").write_text("# inert fixture only\nprint('" + FLAG + "')\n", encoding="utf-8")
        (challenge / "work/writeup.md").write_text("# Writeup\nObserved " + FLAG + "\n" + str(root) + "/" + identifier, encoding="utf-8")
        (challenge / "NOTES.md").write_text("# Notes\nHypothesis precedes observation.\n", encoding="utf-8")
        (archive / "events/local-benchmark/NOTES.md").write_text("# Intake\nLocal-only.\n", encoding="utf-8")
        phase_names = ["claude_solve", "codex_review", "claude_finalize"] if arm == "project_harness" else [arm.removesuffix("_raw") + "_solve"]
        phases = []
        for phase_name in phase_names:
            logs = root / "logs" / identifier / "phases" / phase_name
            logs.mkdir(parents=True)
            rows = [
                {"type": "system", "subtype": "init", "cwd": str(archive), "api_key": "EXCLUDED_INIT_CREDENTIAL"},
                {"type": "assistant", "message": {"content": [
                    {"type": "thinking", "thinking": "Hypothesis: " + FLAG},
                    {"type": "tool_use", "id": "tool-1", "name": "Bash", "input": {
                        "command": "wsl -d ubuntu-ctf -- python -I " + str(root) + "/" + identifier + "/" + instance + "/work/solve.py",
                        "api_key": "EXCLUDED_TOOL_CREDENTIAL"}}]}},
                {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "tool-1", "content": "Observation " + FLAG}]}},
                {"type": "item.completed", "item": {"id": "cmd-2", "type": "command_execution", "command": "wsl -- uname -a", "aggregated_output": "trusted fixture output", "exit_code": 0, "status": "completed"}},
                {"type": "item.completed", "item": {"id": "reason-3", "type": "agent_message", "phase": "commentary", "text": "A judgment based on the observation."}},
                {"type": "turn.completed", "usage": {"input_tokens": 1234}},
                {"type": "unexpected_tool_event", "output": {"password": "EXCLUDED_UNKNOWN_CREDENTIAL", "text": "keep unknown tool evidence"}},
                {"type": "result", "result": FLAG, "subtype": "success", "total_cost_usd": 9876},
            ]
            (logs / "stdout.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            (logs / "stderr.txt").write_text("AWS_SESSION_TOKEN=EXCLUDED_ENV_CREDENTIAL\nfixture warning\n", encoding="utf-8")
            (logs / "prompt.txt").write_text("Work in " + str(archive) + "; no external access.\n", encoding="utf-8")
            phase = {"name": phase_name, "log_dir": "logs/" + identifier + "/phases/" + phase_name,
                     "process_started": True, "status": "completed", "exit_code": 0, "timeout": False, "turn_completed": True}
            if phase_name == "codex_review":
                phase["review_integrity"] = {"before_digest": "1" * 64, "after_digest": "1" * 64, "verified": True, "enforcement": "exclude-me"}
            phases.append(phase)
        write_json(root / "results" / (identifier + ".json"), {**spec, "archive_path": "trials/" + identifier,
            "phases": phases, "model_calls": len(phases), "correct": True, "originals_unchanged": True,
            "status": "completed", "final": FLAG, "usage": {"tokens": 4321}, "verification": {
                "same_instance": True, "new_instance": True, "unseen_commitment_match": True,
                "private_answer": "EXCLUDED_VERIFIER_OTHER"}})
    write_json(root / "protocol.json", {"protocol_version": 6, "suite_version": 3, "specs": specs})
    return specs


class ReviewBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name)
        self.source = self.parent / "run"
        self.specs = fixture(self.source)
        self.dest = self.parent / "reviewer"
        self.mapping = self.parent / "private/mapping.json"

    def export(self, **kwargs):
        return exporter.build_bundle(self.source, kwargs.get("destination", self.dest),
                                     kwargs.get("mapping", self.mapping), kwargs.get("seed", "fixed-public-shuffle-seed"))

    def test_redaction_allowlist_source_immutability_and_line_references(self):
        before = {str(path.relative_to(self.source)): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in self.source.rglob("*") if path.is_file()}
        result = self.export()
        self.assertEqual(result["trial_count"], 3)
        combined = "\n".join(path.read_text() for path in self.dest.rglob("*") if path.is_file())
        for absent in [FLAG, str(self.source), *[spec["id"] for spec in self.specs], "lcg_stream-r1", "claude_raw", "codex_raw", "project_harness",
                       "EXCLUDED_INPUT_CONTENT", "EXCLUDED_GIT_CONTENT", "EXCLUDED_HARNESS_CONTENT", "EXCLUDED_INIT_CREDENTIAL",
                       "EXCLUDED_TOOL_CREDENTIAL", "EXCLUDED_UNKNOWN_CREDENTIAL", "EXCLUDED_ENV_CREDENTIAL", "EXCLUDED_VERIFIER_OTHER"]:
            self.assertNotIn(absent, combined)
        self.assertIn("REDACTED_FLAG", combined)
        self.assertIn("REDACTED_CREDENTIAL", combined)
        self.assertIn("keep unknown tool evidence", combined)
        self.assertIn('"line": 2', combined)
        self.assertIn('"line": 8', combined)
        self.assertNotIn('"input_tokens"', combined)
        self.assertNotIn('"total_cost_usd"', combined)
        self.assertNotIn('"enforcement"', combined)
        self.assertEqual(before, {str(path.relative_to(self.source)): hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in self.source.rglob("*") if path.is_file()})
        self.assertEqual(json.loads(self.mapping.read_text())["trials"]["trial-001"]["phases"].keys(),
                         {path.name for path in (self.dest / "trial-001/phases").iterdir()})
        rubric = exporter.RUBRIC.read_text(encoding="utf-8")
        self.assertIn(rubric, (self.dest / "REVIEW-INSTRUCTIONS.md").read_text())

    def test_deterministic_order_and_bytes_and_explicit_seed_changes_order(self):
        self.export()
        dest2, mapping2 = self.parent / "reviewer2", self.parent / "mapping2.json"
        self.export(destination=dest2, mapping=mapping2)
        self.assertEqual({str(p.relative_to(self.dest)): p.read_bytes() for p in self.dest.rglob("*") if p.is_file()},
                         {str(p.relative_to(dest2)): p.read_bytes() for p in dest2.rglob("*") if p.is_file()})
        initial = json.loads(self.mapping.read_text())["trials"]
        orders = []
        for number in range(4):
            out, mapping = self.parent / f"shuffle-{number}", self.parent / f"map-{number}.json"
            self.export(destination=out, mapping=mapping, seed=f"other-seed-{number}")
            orders.append(json.loads(mapping.read_text())["trials"])
        self.assertTrue(any(order != initial for order in orders))

    def test_refuse_incomplete_run_before_any_write(self):
        (self.source / "results" / (self.specs[0]["id"] + ".json")).unlink()
        with self.assertRaisesRegex(ValueError, "complete run"):
            self.export()
        self.assertFalse(self.dest.exists())

    def test_refuse_active_and_wrong_suite(self):
        (self.source / "active/trial.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "active"):
            self.export()
        (self.source / "active/trial.json").unlink()
        data = json.loads((self.source / "protocol.json").read_text())
        data["suite_version"] = 2
        write_json(self.source / "protocol.json", data)
        with self.assertRaisesRegex(ValueError, "suite v3"):
            self.export()

    def test_native_incoming_archive_is_refused(self):
        (self.source / "trials/.incoming-fixture").mkdir()
        with self.assertRaisesRegex(ValueError, "partial or unexpected"):
            self.export()
        self.assertFalse(self.dest.exists())

    def test_refuse_overlap_mapping_inside_bundle_and_nonempty_destination(self):
        with self.assertRaisesRegex(ValueError, "separate"):
            self.export(destination=self.source / "reviewer")
        with self.assertRaisesRegex(ValueError, "outside"):
            self.export(mapping=self.dest / "mapping.json")
        with self.assertRaisesRegex(ValueError, "modify the source"):
            self.export(mapping=self.source / "reviews/map.json")
        self.dest.mkdir()
        (self.dest / "existing").write_text("keep me")
        with self.assertRaisesRegex(ValueError, "empty"):
            self.export()
        self.assertEqual((self.dest / "existing").read_text(), "keep me")

    def test_refuse_archive_symlink_even_when_excluded(self):
        if os.name == "nt":
            self.skipTest("Symlink fixture is executed in WSL")
        archive = self.source / "trials" / self.specs[0]["id"]
        (archive / ".git/symlink").symlink_to(self.source / "protocol.json")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            self.export()
        self.assertFalse(self.dest.exists())

    def test_refuse_destination_symlink_and_component_traversal(self):
        if os.name == "nt":
            self.skipTest("Symlink fixture is executed in WSL")
        target = self.parent / "actual-dest"
        target.mkdir()
        self.dest.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            self.export()
        self.dest.unlink()
        data = json.loads((self.source / "protocol.json").read_text())
        data["specs"][0]["instance"] = "../outside"
        write_json(self.source / "protocol.json", data)
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            self.export()

    def test_refuse_result_or_phase_path_mismatch_and_phase_count(self):
        path = self.source / "results" / (self.specs[0]["id"] + ".json")
        original = json.loads(path.read_text())
        for field, replacement, message in [("archive_path", "../outside", "archive path"), ("model_calls", 99, "phase count")]:
            data = {**original, field: replacement}
            write_json(path, data)
            with self.assertRaisesRegex(ValueError, message):
                self.export()
        original["phases"][0]["log_dir"] = "../outside"
        write_json(path, original)
        with self.assertRaisesRegex(ValueError, "phase log path"):
            self.export()
        self.assertFalse(self.dest.exists())

    def test_seed_and_key_are_never_read_and_unknown_events_preserved(self):
        actual = exporter.read_text
        opened = []
        def audited(path):
            opened.append(str(path))
            self.assertNotIn("master-seed", str(path))
            self.assertNotIn("answer-key", str(path))
            self.assertNotIn("untrusted", str(path))
            return actual(path)
        with mock.patch.object(exporter, "read_text", side_effect=audited):
            self.export()
        self.assertTrue(opened)

    def test_background_diagnostic_and_file_change_are_not_silently_dropped(self):
        diagnostic = exporter.normalized_event({"type": "system", "subtype": "task_started", "task_id": "bg-1", "message": "background command started"})
        self.assertEqual(diagnostic["event"]["subtype"], "task_started")
        changed = exporter.normalized_event({"type": "item.completed", "item": {"type": "file_change", "changes": [{"path": "work/solve.py", "diff": "fixture diff"}]}})
        self.assertEqual(changed["item"]["changes"][0]["diff"], "fixture diff")

    def test_windows_wsl_temp_paths_and_credentials(self):
        redactor = exporter.Redactor(Path("/mnt/e/Benchmarks/run"), self.specs)
        text = redactor.text("E:\\Benchmarks\\run\\claude_raw-lcg_stream-r1 C:\\Users\\alice\\AppData\\Local\\Temp\\ctf-bench-trial-abc\\workspace\n"
                             "E:\\\\Benchmarks\\\\run\\\\claude_raw-lcg_stream-r1 C:\\\\Users\\\\alice\\\\AppData\\\\Local\\\\Temp\\\\ctf-bench-trial-abc\\\\workspace\n"
                             "/mnt/c/Users/alice/AppData/Local/Temp/ctf-bench-trial-xyz/workspace\n"
                             "C:\\Users\\First Last\\AppData\\Local\\Temp\\ctf-bench-trial-xyz\\workspace\n"
                             "/mnt/c/Users/First Last/AppData/Local/Temp/ctf-bench-trial-xyz/workspace\n"
                             "/tmp/ctf-bench-trial-test/workspace " + FLAG + "\nAPI_TOKEN=very-secret-value")
        for value in ["alice", "First Last", "ctf-bench-trial", "claude_raw", "lcg_stream-r1", "very-secret-value", FLAG]:
            self.assertNotIn(value, text)
        self.assertIn("RUN_ROOT", text)
        self.assertIn("TRIAL_TEMP", text)
        self.assertIn("REDACTED_CREDENTIAL", text)

    def test_unexecuted_trial_stays_unrated(self):
        path = self.source / "results" / (self.specs[0]["id"] + ".json")
        data = json.loads(path.read_text())
        data["phases"] = []
        data["model_calls"] = 0
        data["status"] = "infrastructure_error"
        write_json(path, data)
        self.export()
        mapping = json.loads(self.mapping.read_text())["trials"]
        label = next(label for label, entry in mapping.items() if entry["trial_id"] == self.specs[0]["id"])
        self.assertFalse(json.loads((self.dest / label / "RESULT.json").read_text())["executed"])
        self.assertIn("Unexecuted trials remain\nunrated, not zero", (self.dest / "REVIEW-INSTRUCTIONS.md").read_text())


if __name__ == "__main__":
    unittest.main()
