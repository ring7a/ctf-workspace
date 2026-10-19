"""Verifier orchestration tests: inert inputs, mocked generation and execution."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verifier_under_test", ROOT / "benchmarks/verify_solution.py")
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class DeterministicVerifier(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ctf-verifier-unit-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.seed_file = self.root / "private/master-seed.bin"
        self.seed_file.parent.mkdir()
        self.seed_file.write_bytes(hashlib.sha256(b"public inert verifier fixture seed").digest())
        self.work = self.root / "work"
        self.work.mkdir()
        (self.work / "solve.py").write_text("# inert existence fixture; never executed\n")
        self.first = self.root / "main-input"
        self.first.mkdir()
        (self.first / "fixture.txt").write_text("inert main input\n")
        self.generated = []
        self.calls = []
        self.suite = SimpleNamespace(generate=self.generate_fixture)

    def generate_fixture(self, root, repeats, seed, *, domain, tasks):
        # Deterministic data fixture only, without a CTF task or plaintext flag.
        self.generated.append(root)
        self.calls.append((repeats, domain, tuple(tasks)))
        manifest = {}
        for task in tasks:
            for repeat in range(1, repeats + 1):
                instance = f"{task}-r{repeat}"
                folder = root / instance / "untrusted"
                folder.mkdir(parents=True)
                data = hashlib.sha256(seed + domain.encode() + instance.encode()).hexdigest().encode()
                (folder / "fixture.txt").write_bytes(data)
                manifest[instance] = {"hashes": {"fixture.txt": hashlib.sha256(data).hexdigest()},
                                      "flag_sha256": hashlib.sha256(b"INERT_EXPECTED").hexdigest()}
        return manifest

    @staticmethod
    def execution_fixture(script, inputs):
        return verifier.execution_summary(0, b"INERT_OUTPUT", b"")

    def test_preparation_returns_commitments_only_and_removes_trusted_unseen(self):
        with mock.patch.object(verifier, "load_suite", return_value=self.suite), \
             mock.patch.object(verifier, "verify", side_effect=AssertionError("No script in preparation")):
            commitments = verifier.unseen_commitments(self.seed_file, 2, ["fixture"])
        self.assertEqual(set(commitments), {"fixture-r1", "fixture-r2"})
        self.assertEqual(self.calls, [(2, "unseen", ("fixture",))])
        for entry in commitments.values():
            self.assertEqual(set(entry), {"hashes", "input_digest", "flag_sha256"})
            canonical = json.dumps(entry["hashes"], sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            self.assertEqual(entry["input_digest"], hashlib.sha256(canonical.encode()).hexdigest())
        self.assertTrue(all(not path.parent.exists() for path in self.generated))
        serialized = json.dumps(commitments)
        self.assertFalse(self.seed_file.read_bytes().hex() in serialized)
        self.assertNotIn(str(self.seed_file), serialized)
        self.assertNotIn("INERT_EXPECTED", serialized)

    def test_every_arm_regenerates_byte_identical_paired_unseen_inputs(self):
        observed_inputs = []

        def inspect_execution(script, inputs):
            if inputs != self.first:
                observed_inputs.append((inputs / "fixture.txt").read_bytes())
                self.assertFalse((inputs / "master-seed.bin").exists())
                self.assertFalse((inputs / "make_suite.py").exists())
            return self.execution_fixture(script, inputs)

        with mock.patch.object(verifier, "load_suite", return_value=self.suite), \
             mock.patch.object(verifier, "verify", side_effect=inspect_execution):
            commitment = verifier.unseen_commitments(self.seed_file, 2, ["fixture"])["fixture-r2"]
            results = [verifier.verify_instance(self.work, self.first, "fixture-r2", self.seed_file)
                       for _ in ("claude_raw", "codex_raw", "project_harness")]
        self.assertEqual(len(observed_inputs), 3)
        self.assertEqual(len(set(observed_inputs)), 1)
        for result in results:
            self.assertEqual(result["status"], "ran")
            self.assertEqual(result["same_execution"]["returncode"], 0)
            self.assertEqual(result["new_execution"]["returncode"], 0)
            self.assertEqual(result["unseen_input_digest"], commitment["input_digest"])
            self.assertEqual(result["unseen_hashes"], commitment["hashes"])
            self.assertEqual(result["new_expected_flag_sha256"], commitment["flag_sha256"])
        self.assertTrue(all(not path.parent.exists() for path in self.generated))

    def test_verification_result_never_contains_raw_streams_flags_or_unseen_echo(self):
        flag = b"BENCH{" + b"1" * 32 + b"}"
        raw_unseen = b"INERT_UNSEEN_CONTENT\n" + flag + b"\n"
        executions = [verifier.execution_summary(0, flag + b"\n", b"main diagnostic"),
                      verifier.execution_summary(0, raw_unseen, b"unseen diagnostic")]
        with mock.patch.object(verifier, "load_suite", return_value=self.suite), \
             mock.patch.object(verifier, "verify", side_effect=executions):
            result = verifier.verify_instance(self.work, self.first, "fixture-r1", self.seed_file)
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(flag.decode(), serialized)
        self.assertNotIn("INERT_UNSEEN_CONTENT", serialized)
        self.assertNotIn("main diagnostic", serialized)
        self.assertNotIn("unseen diagnostic", serialized)
        self.assertFalse(any(key.endswith("stdout") or key.endswith("stderr") for key in result))
        self.assertEqual(result["new_execution"]["candidate_flag_sha256s"],
                         [hashlib.sha256(flag).hexdigest()])
        self.assertEqual(result["new_execution"]["candidate_flag_count"], 1)

    def test_failed_generation_still_removes_trusted_temp(self):
        def fail_generation(*args, **kwargs):
            self.generate_fixture(*args, **kwargs)
            raise ValueError("inert generator failure")
        with mock.patch.object(verifier, "load_suite", return_value=SimpleNamespace(generate=fail_generation)):
            with self.assertRaises(ValueError):
                verifier.unseen_commitments(self.seed_file, 1, ["fixture"])
        self.assertTrue(all(not path.parent.exists() for path in self.generated))

    def test_bad_seed_length_fails_before_generation_or_execution(self):
        self.seed_file.write_bytes(b"invalid")
        with mock.patch.object(verifier, "load_suite", side_effect=AssertionError("No generation")), \
             mock.patch.object(verifier, "verify", side_effect=AssertionError("No execution")):
            with self.assertRaises(ValueError):
                verifier.verify_instance(self.work, self.first, "fixture-r1", self.seed_file)

    @unittest.skipUnless(os.name == "posix" and Path("/home/ctf/.ctf-tools/venv").exists(), "WSL deterministic API integration")
    def test_real_suite_api_commitment_matches_regeneration_in_wsl(self):
        # Exercise the real deterministic generator only in the required WSL
        # environment. Submitted-script execution remains a mock throughout.
        suite = verifier.load_suite()
        main = suite.generate(self.root / "main-generated", 2, verifier.read_seed(self.seed_file),
                              domain="main", tasks=["layered"])
        commitments = verifier.unseen_commitments(self.seed_file, 2, ["layered"])
        self.assertNotEqual(main["layered-r2"]["hashes"], commitments["layered-r2"]["hashes"])
        with mock.patch.object(verifier, "verify", side_effect=self.execution_fixture):
            results = [verifier.verify_instance(self.work, self.first, "layered-r2", self.seed_file)
                       for _ in range(3)]
        self.assertEqual(len({item["unseen_input_digest"] for item in results}), 1)
        for result in results:
            self.assertEqual(result["unseen_input_digest"], commitments["layered-r2"]["input_digest"])
            self.assertEqual(result["unseen_hashes"], commitments["layered-r2"]["hashes"])
            self.assertEqual(result["new_expected_flag_sha256"], commitments["layered-r2"]["flag_sha256"])

    def test_bwrap_argv_never_mounts_seed_generator_or_host_workspace(self):
        def capture(command, **kwargs):
            self.assertIn("--unshare-all", command)
            self.assertIn("--die-with-parent", command)
            self.assertIn("--clearenv", command)
            self.assertNotIn(str(self.seed_file), command)
            self.assertNotIn(str(ROOT), command)
            self.assertNotIn(str(self.work), command)
            self.assertEqual(command[-3:], ["-I", "/work/solve.py", "/input"])
            kwargs["stdout"].write(b"INERT\n")
            return SimpleNamespace(returncode=0)
        with mock.patch.object(verifier.subprocess, "run", side_effect=capture):
            result = verifier.verify(self.work / "solve.py", self.first)
        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["stdout_bytes"], len(b"INERT\n"))
        self.assertEqual(result["stdout_sha256"], hashlib.sha256(b"INERT\n").hexdigest())
        self.assertEqual(result["stderr_bytes"], 0)
        self.assertEqual(result["candidate_flag_sha256s"], [])
        self.assertNotIn("stdout", result)
        self.assertNotIn("stderr", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
