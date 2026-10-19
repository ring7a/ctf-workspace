"""Unit tests of the measurement code, not CTF solve results."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "benchmarks" / (name + ".py"))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


runner = module("run_benchmark")
summary = module("summarize")


class Measurements(unittest.TestCase):
    def test_intake_fails_closed(self):
        with self.assertRaises(ValueError):
            runner.check_intake(ROOT / "benchmarks" / "intake.example.json")

    def test_codex_final_does_not_use_tool_output(self):
        log = '\n'.join(json.dumps(e) for e in [
            {"type": "item.completed", "item": {"type": "command_execution", "aggregated_output": "BENCH{00000000000000000000000000000000}"}},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "unsolved"}},
            {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 2}},
        ])
        parsed = runner.parse_events("codex", log)
        self.assertEqual(parsed["final"], "unsolved")
        self.assertEqual(parsed["tool_calls"], 1)
        self.assertEqual(parsed["usage"]["output_tokens"], 2)

    def test_claude_usage_and_model(self):
        log = '\n'.join(json.dumps(e) for e in [
            {"type": "system", "model": "test-model"},
            {"type": "result", "result": "unsolved", "usage": {"input_tokens": 3}, "total_cost_usd": 0.1},
        ])
        parsed = runner.parse_events("claude", log)
        self.assertEqual(parsed["observed_model"], "test-model")
        self.assertEqual(parsed["usage"]["reported_cost_usd"], 0.1)

    def test_interrupted_turn_is_not_completed(self):
        event = {"type": "item.completed", "item": {"type": "agent_message", "text": "candidate"}}
        self.assertFalse(runner.parse_events("codex", json.dumps(event))["turn_completed"])

    def test_commentary_not_final(self):
        event = {"type": "item.completed", "item": {"type": "agent_message", "phase": "commentary", "text": "candidate"}}
        self.assertEqual(runner.parse_events("codex", json.dumps(event))["final"], "")

    def test_wilson_zero_and_all(self):
        self.assertEqual(summary.wilson(0, 0), [None, None])
        self.assertEqual(summary.wilson(0, 10)[0], 0)
        self.assertEqual(summary.wilson(10, 10)[1], 1)
        self.assertGreater(summary.wilson(0, 10)[1], 0)
        self.assertLess(summary.wilson(10, 10)[0], 1)

    def test_missing_rows_not_counted_as_observed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            seed = hashlib.sha256(b"inert summary aggregate master seed").digest()
            (root / ".private").mkdir()
            (root / ".private/master-seed.bin").write_bytes(seed)
            specs = [{"id": f"{arm}-dummy-r1", "arm": arm, **summary.ARM_METADATA[arm],
                      "task": "dummy", "instance": "dummy-r1", "repeat": 1}
                     for arm in summary.ARMS]
            protocol = {"protocol_version": summary.PROTOCOL_VERSION, "arms": list(summary.ARMS),
                        "phase_plans": summary.phase_protocol(), "timeout": summary.TOTAL_BUDGET_SECONDS,
                        "provider_execution": summary.PROVIDER_EXECUTION,
                        "workers": 1, "tasks": ["dummy"], "repeats": 1,
                        "claude_model": "claude-test-model", "codex_model": "codex-test-model",
                        "specs": specs}
            hashes = {"fixture.txt": hashlib.sha256(b"inert unseen metadata").hexdigest()}
            canonical = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                                               ensure_ascii=True).encode()).hexdigest()
            commitments = {"dummy-r1": {"hashes": hashes, "input_digest": canonical(hashes),
                                        "flag_sha256": hashlib.sha256(b"inert expected output").hexdigest()}}
            answer_key = {"dummy-r1": {"flag_sha256": hashlib.sha256(
                b"inert expected output").hexdigest()}}
            (root / "suite").mkdir()
            (root / "suite/answer-key.json").write_text(
                json.dumps(answer_key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            protocol.update(suite_version=summary.SUITE_VERSION, master_seed_sha256=hashlib.sha256(seed).hexdigest(),
                            unseen_commitments=commitments, unseen_commitments_sha256=canonical(commitments),
                            suite_hashes=summary.tree_hashes(root / "suite"),
                            benchmark_code_hashes=summary.benchmark_code_hashes())
            protocol[summary.PROTOCOL_HMAC_FIELD] = summary.compute_protocol_hmac(
                protocol, summary.derive_protocol_hmac_key(seed))
            (root / "protocol.json").write_text(json.dumps(protocol))
            result = summary.aggregate(
                root, commitment_regenerator=lambda _root, value: value["unseen_commitments"])
            self.assertEqual(result["observed"], 0)
            self.assertEqual(result["missing"], 3)
            self.assertFalse(result["primary_metric_ready"])

    @unittest.skipUnless(os.name == "posix" and Path("/home/ctf/.ctf-tools/venv").exists(), "WSL bwrap smoke")
    def test_verifier_hides_host_files(self):
        verifier = module("verify_solution")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "input").mkdir()
            script = root / "solve.py"
            script.write_text("from pathlib import Path\nassert not Path('/mnt').exists()\nassert not Path('/root').exists()\nprint('SANDBOX_OK')\n")
            result = verifier.verify(script, root / "input")
            self.assertEqual(result["returncode"], 0)
            self.assertEqual(result["stdout_sha256"], hashlib.sha256(b"SANDBOX_OK\n").hexdigest())


if __name__ == "__main__":
    unittest.main()
