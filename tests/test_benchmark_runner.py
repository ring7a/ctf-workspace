"""Lifecycle regression tests using mocks and inert text fixtures only.

No native CLI, WSL command, model, challenge generator or submitted script runs.
Run: python -I tests/test_benchmark_runner.py
"""
from contextlib import redirect_stdout
from collections import Counter
import hashlib
import hmac
import importlib.util
import io
import json
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest import mock
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
MODULE_SPEC = importlib.util.spec_from_file_location(
    "benchmark_runner_lifecycle_test", ROOT / "benchmarks/run_benchmark.py"
)
runner = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(runner)
SUMMARY_SPEC = importlib.util.spec_from_file_location(
    "benchmark_summary_for_runner_test", ROOT / "benchmarks/summarize.py"
)
summary = importlib.util.module_from_spec(SUMMARY_SPEC)
SUMMARY_SPEC.loader.exec_module(summary)

# A literal parser fixture, never a generated challenge or a model answer.
CANDIDATE = "BENCH{" + "0" * 32 + "}"
DIGEST = hashlib.sha256(CANDIDATE.encode()).hexdigest()
FIXTURE_SEED = hashlib.sha256(b"inert public unit-test seed fixture").digest()


def unseen_fixture(instance):
    hashes = {"fixture.txt": hashlib.sha256(b"inert unseen input fixture").hexdigest()}
    return {instance: {"hashes": hashes, "input_digest": runner.tree_digest(hashes), "flag_sha256": DIGEST}}


def execution_fixture(returncode=0, candidate=CANDIDATE, *, stderr=b""):
    stdout = ((candidate + "\n").encode("ascii") if candidate is not None else b"")
    candidates = re.findall(rb"BENCH\{[0-9a-f]{32}\}", stdout)
    return {"returncode": returncode, "stdout_bytes": len(stdout),
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_bytes": len(stderr), "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
            "candidate_flag_sha256s": sorted({hashlib.sha256(value).hexdigest() for value in candidates}),
            "candidate_flag_count": len(candidates)}


def private_fixture(root, instance):
    path = root / runner.MASTER_SEED_PATH
    path.parent.mkdir()
    path.write_bytes(FIXTURE_SEED)
    commitments = unseen_fixture(instance)
    return {"master_seed_sha256": hashlib.sha256(FIXTURE_SEED).hexdigest(),
            "unseen_commitments": commitments, "unseen_commitments_sha256": runner.tree_digest(commitments)}


class FakeProcess:
    """Only the Popen operations exercised by the runner; no OS process exists."""

    def __init__(self, stdout, log, *, communicate_error=None, exit_code=0):
        self.pid = 424242
        self.returncode = None
        self.stdout_handle = stdout
        self.log = log
        self.communicate_error = communicate_error
        self.exit_code = exit_code
        self.communicate_hook = None
        self.communicate_calls = []
        self.wait_calls = []

    def communicate(self, prompt, timeout):
        self.communicate_calls.append((prompt, timeout))
        self.stdout_handle.write(self.log)
        self.stdout_handle.flush()
        if self.communicate_hook:
            self.communicate_hook()
        if self.communicate_error:
            raise self.communicate_error
        if self.returncode is None:
            self.returncode = self.exit_code
        return None, None

    def poll(self):
        return self.returncode

    def wait(self, timeout):
        self.wait_calls.append(timeout)
        if self.returncode is None:
            self.returncode = -9
        return self.returncode


class TrialLifecycle(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ctf-runner-mock-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        active_base = tempfile.TemporaryDirectory(prefix="ctf-active-fixtures-")
        self.addCleanup(active_base.cleanup)
        self.active_base = Path(active_base.name)
        allocate_temp = tempfile.mkdtemp
        self.allocate = self.patch("tempfile", new=SimpleNamespace(
            mkdtemp=mock.Mock(side_effect=lambda **kwargs: allocate_temp(dir=self.active_base, **kwargs))))
        self.active_trial = None
        runner.install_guards(self.root)
        self.spec = {"id": "codex_raw-mock-r1", "arm": "codex_raw", "provider": "codex",
                     "condition": "raw", "instance": "mock-r1",
                     "task": "layered", "repeat": 1}
        self.args = SimpleNamespace(timeout=240, claude="FAKE_CLAUDE", codex="FAKE_CODEX",
                                    claude_model="fake-claude-model", codex_model="fake-codex-model")
        self.intake = {"user_confirmation": "UNIT TEST FIXTURE ONLY"}
        self.input = self.root / "suite/mock-r1/untrusted"
        self.input.mkdir(parents=True)
        data = b"Inert measurement fixture; there is no puzzle or solution here.\n"
        (self.input / "fixture.txt").write_bytes(data)
        self.key = {"mock-r1": {"flag_sha256": DIGEST,
                               "hashes": {"fixture.txt": hashlib.sha256(data).hexdigest()}}}
        (self.root / "harness-snapshot").mkdir()
        self.args.artifact_hashes = {"suite_hashes": runner.tree_hashes(self.root / "suite"),
                                     "harness_hashes": runner.tree_hashes(self.root / "harness-snapshot"),
                                     "benchmark_code_hashes": runner.benchmark_code_hashes(),
                                     **private_fixture(self.root, "mock-r1")}
        runner.STOP.clear()
        runner.ACTIVE.clear()
        self.addCleanup(runner.STOP.clear)
        self.addCleanup(runner.ACTIVE.clear)
        # All outward execution surfaces are mocked, including git and taskkill.
        self.run = self.patch("run", return_value=SimpleNamespace(returncode=0, stdout="", stderr=""))
        self.verifier = self.patch("wsl_python", side_effect=AssertionError("Unexpected verifier call"))
        self.cli_paths = {"FAKE_CLAUDE": str(self.active_base / "installed/claude.exe"),
                          "FAKE_CODEX": str(self.active_base / "installed/codex.exe")}
        self.cli_resolver = self.patch("resolve_cli", side_effect=self.cli_paths.__getitem__)
        self.patch("wsl_path", side_effect=lambda p: Path(p).as_posix())
        no_window = mock.patch.object(runner.subprocess, "CREATE_NO_WINDOW", 0, create=True)
        no_window.start()
        self.addCleanup(no_window.stop)
        self.popen = mock.patch.object(runner.subprocess, "Popen", side_effect=self.make_process)
        self.popen_mock = self.popen.start()
        self.addCleanup(self.popen.stop)
        self.log = self.completed_log()
        self.communicate_error = None
        self.exit_code = 0
        self.process_hook = None
        self.proc = None
        self.processes = []
        self.phase_configs = []
        self.create_script = False

    def patch(self, name, **kwargs):
        patcher = mock.patch.object(runner, name, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    @staticmethod
    def completed_log(completed=True, final=CANDIDATE):
        events = [{"type": "item.completed", "item": {
            "type": "agent_message", "phase": "final_answer", "text": final}}]
        if completed:
            events.append({"type": "turn.completed", "usage": {"output_tokens": 4}})
        return "\n".join(map(json.dumps, events)) + "\n"

    @staticmethod
    def claude_log(final=CANDIDATE, completed=True):
        events = [{"type": "system", "model": "observed-claude"},
                  {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read"}]}}]
        if completed:
            events.append({"type": "result", "subtype": "success", "result": final,
                           "usage": {"input_tokens": 3, "output_tokens": 7}, "total_cost_usd": 0.01})
        return "\n".join(map(json.dumps, events)) + "\n"

    def use_harness(self):
        self.spec.update(id="project_harness-mock-r1", arm="project_harness",
                         provider="claude+codex", condition="harness")
        snapshot = self.root / "harness-snapshot"
        (snapshot / ".claude/skills/fixture").mkdir(parents=True)
        (snapshot / "AGENTS.md").write_text("# inert harness marker\n")
        (snapshot / ".claude/skills/fixture/SKILL.md").write_text("# inert reference fixture\n")
        (snapshot / "tools").mkdir()
        (snapshot / "tools/codex-crosscheck.sh").write_bytes(runner.CROSSCHECK_DISABLED.encode("utf-8"))
        self.args.artifact_hashes["harness_hashes"] = runner.tree_hashes(snapshot)
        self.phase_configs = [{"log": self.claude_log()},
                              {"log": self.completed_log(final="Review: check the parser boundary.")},
                              {"log": self.claude_log()}]

    @property
    def trial(self):
        if self.active_trial is not None and self.active_trial.exists():
            return self.active_trial
        return self.archive

    @property
    def archive(self):
        return self.root / "trials" / self.spec["id"]

    @property
    def pointer(self):
        return runner.pointer_path(self.root, self.spec)

    @property
    def work(self):
        return self.trial / "events/local-benchmark/challenges/mock-r1/work"

    @property
    def result_path(self):
        return self.root / "results" / (self.spec["id"] + ".json")

    def make_process(self, command, **kwargs):
        self.active_trial = Path(kwargs["cwd"])
        index = len(self.processes)
        config = self.phase_configs[index] if self.phase_configs else {}
        self.proc = FakeProcess(kwargs["stdout"], config.get("log", self.log),
                                communicate_error=config.get("communicate_error", self.communicate_error),
                                exit_code=config.get("exit_code", self.exit_code))
        self.proc.pid += index
        self.processes.append(self.proc)
        kwargs["stderr"].write(f"inert phase {index + 1} stderr\n")
        if self.create_script:
            # Existence fixture only. wsl_python is mocked; this file is never run.
            (self.work / "solve.py").write_text("# inert existence fixture\n")
        if self.process_hook:
            self.process_hook(self.proc)
        return self.proc

    def invoke(self):
        with redirect_stdout(io.StringIO()):
            return runner.process_trial_safe(self.root, self.spec, self.intake, self.args, self.key)

    def stored(self):
        return json.loads(self.result_path.read_text())

    def write_signed_result(self, **changes):
        self.archive.mkdir(parents=True)
        (self.archive / "inert-archive.txt").write_text("authenticated archive fixture\n")
        saved = {**self.spec, "status": "completed", "correct": True, "marker": "KEEP",
                 "archive_path": self.archive.relative_to(self.root).as_posix(),
                 "archive_tree_digest": runner.tree_digest(runner.tree_hashes(self.archive))}
        saved.update(changes)
        saved["result_hmac_sha256"] = runner.result_hmac_sha256(self.root, saved)
        runner.save(self.result_path, saved)
        return saved

    def kill_commands(self):
        return [call.args[0] for call in self.run.call_args_list
                if call.args[0][0] == "taskkill"]

    def verifier_result(self, *, process_code=0, same_code=0, new_code=0):
        self.create_script = True
        self.verifier.side_effect = None
        commitment = self.args.artifact_hashes["unseen_commitments"]["mock-r1"]
        self.verifier.return_value = SimpleNamespace(
            returncode=process_code, stderr="", stdout=json.dumps({
                "status": "ran", "same_execution": execution_fixture(same_code),
                "new_execution": execution_fixture(new_code),
                "unseen_hashes": commitment["hashes"],
                "unseen_input_digest": commitment["input_digest"],
                "new_expected_flag_sha256": commitment["flag_sha256"],
            }))

    def test_completed_model_candidate_is_recorded_without_reproduction_claim(self):
        result = self.invoke()
        self.assertTrue(result["correct"])
        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["verification"]["same_instance"])
        self.assertEqual(result, self.stored())
        self.assertEqual(runner.ACTIVE, {})
        self.assertEqual(self.kill_commands(), [])

    def test_private_seed_tamper_halts_before_any_model(self):
        (self.root / runner.MASTER_SEED_PATH).write_bytes(b"x" * 32)
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.popen_mock.assert_not_called()
        self.assertTrue(runner.STOP.is_set())
        self.assertFalse(self.result_path.exists())

    def test_private_seed_tamper_during_model_preserves_active_without_score(self):
        self.process_hook = lambda proc: (self.root / runner.MASTER_SEED_PATH).write_bytes(b"x" * 32)
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.assertTrue(self.pointer.exists())
        self.assertTrue(self.active_trial.exists())
        self.assertFalse(self.archive.exists())
        self.assertFalse(self.result_path.exists())

    def test_private_seed_never_enters_workspace_prompt_command_or_environment(self):
        self.use_harness()
        self.invoke()
        self.assertFalse((self.archive / ".private").exists())
        self.assertFalse((self.root / "harness-snapshot/.private").exists())
        self.assertTrue(all(FIXTURE_SEED not in path.read_bytes() for path in self.archive.rglob("*") if path.is_file()))
        for call, proc in zip(self.popen_mock.call_args_list, self.processes):
            material = json.dumps([call.args[0], call.kwargs["env"], proc.communicate_calls])
            self.assertFalse(FIXTURE_SEED.hex() in material)
            self.assertNotIn("master-seed.bin", material)
            self.assertNotIn("answer-key.json", material)

    def test_changed_unseen_commitment_manifest_halts_before_model(self):
        self.args.artifact_hashes["unseen_commitments"]["mock-r1"]["flag_sha256"] = "f" * 64
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.popen_mock.assert_not_called()

    def test_wrong_unseen_input_digest_rejects_verification_but_keeps_model_answer(self):
        self.verifier_result()
        response = json.loads(self.verifier.return_value.stdout)
        response["unseen_input_digest"] = "f" * 64
        self.verifier.return_value.stdout = json.dumps(response)
        result = self.invoke()
        verification = result["verification"]
        self.assertTrue(result["correct"])
        self.assertFalse(verification["new_instance"])
        self.assertFalse(verification["same_instance"])
        self.assertFalse(verification["unseen_digest_match"])
        self.assertFalse(verification["unseen_flag_hash_match"])
        self.assertEqual(verification["status"], "verification_infrastructure_error")

    def test_wrong_unseen_flag_commitment_rejects_new_instance(self):
        self.verifier_result()
        response = json.loads(self.verifier.return_value.stdout)
        response["new_expected_flag_sha256"] = "f" * 64
        self.verifier.return_value.stdout = json.dumps(response)
        result = self.invoke()
        self.assertFalse(result["verification"]["new_instance"])
        self.assertTrue(result["verification"]["unseen_digest_match"])
        self.assertFalse(result["verification"]["unseen_flag_hash_match"])
        self.assertFalse(result["verification"]["unseen_commitment_match"])

    def test_wrong_unseen_hash_mapping_rejects_new_instance_even_with_claimed_flag(self):
        self.verifier_result()
        response = json.loads(self.verifier.return_value.stdout)
        response["unseen_hashes"] = {"fixture.txt": "f" * 64}
        response["unseen_input_digest"] = runner.tree_digest(response["unseen_hashes"])
        self.verifier.return_value.stdout = json.dumps(response)
        result = self.invoke()
        verification = result["verification"]
        self.assertFalse(verification["unseen_hashes_match"])
        self.assertFalse(verification["unseen_digest_match"])
        self.assertTrue(verification["unseen_flag_hash_match"])
        self.assertFalse(verification["unseen_commitment_match"])
        self.assertFalse(verification["new_instance"])

    def test_verification_logs_and_result_never_store_raw_candidate_or_streams(self):
        self.verifier_result()
        result = self.invoke()
        verification_path = self.root / "logs" / self.spec["id"] / "verification.json"
        serialized = verification_path.read_text(encoding="utf-8")
        self.assertNotIn(CANDIDATE, serialized)
        self.assertNotIn("same_stdout", serialized)
        self.assertNotIn("new_stdout", serialized)
        self.assertNotIn(CANDIDATE, json.dumps(result["verification"], sort_keys=True))
        self.assertFalse((verification_path.parent / "verification.stdout").exists())
        self.assertFalse((verification_path.parent / "verification.stderr").exists())

    def test_duplicate_candidate_occurrences_do_not_count_as_single_reproduction(self):
        self.verifier_result()
        response = json.loads(self.verifier.return_value.stdout)
        response["new_execution"]["candidate_flag_count"] = 2
        self.verifier.return_value.stdout = json.dumps(response)
        result = self.invoke()
        self.assertTrue(result["verification"]["unseen_commitment_match"])
        self.assertFalse(result["verification"]["new_instance"])

    def test_missing_script_uses_complete_safe_verification_schema(self):
        result = self.invoke()
        verification = result["verification"]
        self.assertEqual(verification["status"], "missing_script")
        for name in ("same_execution", "new_execution"):
            self.assertEqual(verification[name], runner.empty_execution_evidence())
        self.assertEqual(verification["unseen_hashes"], {})
        self.assertIsNone(verification["new_expected_flag_sha256"])
        self.assertEqual(verification["expected_unseen_hashes"],
                         self.args.artifact_hashes["unseen_commitments"]["mock-r1"]["hashes"])
        self.assertFalse(verification["unseen_commitment_match"])

    def test_all_three_arms_verify_against_one_paired_unseen_commitment(self):
        self.use_harness()
        harness_logs = self.phase_configs.copy()
        self.verifier_result()
        results = []
        for arm in runner.ARMS:
            self.spec.update(id=arm + "-mock-r1", arm=arm,
                             provider="claude+codex" if arm == "project_harness" else arm.removesuffix("_raw"),
                             condition="harness" if arm == "project_harness" else "raw")
            self.processes.clear()
            self.phase_configs = harness_logs if arm == "project_harness" else []
            self.log = self.claude_log() if arm == "claude_raw" else self.completed_log()
            result = self.invoke()
            self.assertTrue(result["verification"]["same_instance"])
            self.assertTrue(result["verification"]["new_instance"])
            self.assertTrue(result["verification"]["unseen_commitment_match"])
            results.append(result)
        self.assertEqual(len({r["verification"]["unseen_input_digest"] for r in results}), 1)
        self.assertTrue(all(r["unseen_commitment"] == results[0]["unseen_commitment"] for r in results))
        for call in self.verifier.call_args_list:
            argv = call.args
            self.assertEqual(argv[argv.index("--instance") + 1], "mock-r1")
            self.assertEqual(argv[argv.index("--master-seed-file") + 1], (self.root / runner.MASTER_SEED_PATH).as_posix())

    def test_active_parents_are_independent_and_contain_only_this_trial(self):
        parents = []
        for arm in ("claude_raw", "codex_raw"):
            spec = {**self.spec, "id": arm + "-mock-r1", "arm": arm}
            state = {}
            trial, _ = runner.prepare_trial(self.root, spec, self.intake, state)
            parents.append(trial.parent)
            self.assertFalse(trial.is_relative_to(self.root))
            self.assertEqual(trial.name, "workspace")
            self.assertTrue(trial.parent.name.startswith("ctf-bench-trial-"))
            self.assertEqual({p.name for p in trial.parent.iterdir()}, {"workspace", "tmp", "runner-guards"})
            self.assertFalse((trial / "AGENTS.md").exists())
            self.assertFalse((trial / ".agents").exists())
            self.assertFalse(any(p.name in {"answer-key.json", "suite", "logs", "results", "trials"}
                                 for p in trial.parent.rglob("*")))
            record = json.loads(state["pointer"].read_text())
            self.assertEqual(record["workspace"], str(trial))
            self.assertEqual(record["state"], "prepared")
        self.assertNotEqual(*parents)

    def test_child_command_prompt_and_environment_use_only_active_workspace(self):
        self.use_harness()
        with mock.patch.dict(runner.os.environ, {"AUTH_FIXTURE": "opaque-test-auth", "OTHER_SETTING": "preserved"}):
            result = self.invoke()
        self.assertEqual(len(self.popen_mock.call_args_list), 3)
        for call, process in zip(self.popen_mock.call_args_list, self.processes):
            command, env = call.args[0], call.kwargs["env"]
            self.assertEqual(Path(call.kwargs["cwd"]), self.active_trial)
            if "--cd" in command:
                self.assertEqual(command[command.index("--cd") + 1], str(self.active_trial))
            prompt = process.communicate_calls[0][0]
            self.assertIn(self.active_trial.as_posix(), prompt)
            hidden = str(self.root).replace("\\", "/").casefold()
            for value in [*command, *env.values(), prompt]:
                self.assertNotIn(hidden, str(value).replace("\\", "/").casefold())
            self.assertEqual(env["AUTH_FIXTURE"], "opaque-test-auth")
            self.assertEqual(env["OTHER_SETTING"], "preserved")
            for field in ("TEMP", "TMP", "TMPDIR"):
                self.assertEqual(env[field], str(self.active_trial.parent / "tmp"))
                self.assertIn(field + "/p", env["WSLENV"].split(":"))
            self.assertNotIn("--restricted", command)
        self.assertEqual(result["execution_workspace"], str(self.active_trial))
        self.assertTrue((self.archive / "AGENTS.md").is_file())

    def test_archive_precedes_result_and_pointer_removal(self):
        order = []
        original_save, original_unlink, original_rename = runner.save, Path.unlink, Path.rename

        def observe_rename(path, target):
            if Path(target) == self.archive:
                self.assertTrue(self.pointer.exists())
                self.assertFalse(self.result_path.exists())
                self.assertTrue(path.name.startswith(".incoming-"))
                order.append("archive")
            return original_rename(path, target)

        def observe_save(path, data):
            if path == self.result_path:
                self.assertTrue(self.archive.is_dir())
                self.assertTrue(self.pointer.exists())
                order.append("result")
            return original_save(path, data)

        def observe_unlink(path, *args, **kwargs):
            if path == self.pointer:
                self.assertTrue(self.archive.is_dir())
                self.assertTrue(self.result_path.is_file())
                order.append("pointer_removed")
            return original_unlink(path, *args, **kwargs)

        self.patch("save", side_effect=observe_save)
        with mock.patch.object(Path, "rename", autospec=True, side_effect=observe_rename), \
             mock.patch.object(Path, "unlink", autospec=True, side_effect=observe_unlink):
            self.invoke()
        self.assertEqual(order, ["archive", "result", "pointer_removed"])
        self.assertFalse(self.active_trial.parent.exists())
        self.assertFalse(self.pointer.exists())
        self.assertEqual(list((self.root / "trials").glob(".incoming-*")), [])

    def test_pointer_alone_blocks_rerun_without_allocating_or_claiming_child(self):
        runner.save(self.pointer, {"workspace": "uninspected", "pid": 424242})
        before = self.pointer.read_bytes()
        with self.assertRaises(runner.RecoveryRequiredError):
            self.invoke()
        self.assertEqual(self.pointer.read_bytes(), before)
        runner.tempfile.mkdtemp.assert_not_called()
        self.popen_mock.assert_not_called()
        self.assertEqual(self.kill_commands(), [])

    def test_archive_copy_failure_preserves_pointer_workspace_and_no_result(self):
        original_copy = runner.shutil.copy2

        def fail_incoming_copy(source, destination, **kwargs):
            if any(part.startswith(".incoming-") for part in Path(destination).parts):
                raise OSError("mock archive disk failure")
            return original_copy(source, destination, **kwargs)

        with mock.patch.object(runner.shutil, "copy2", side_effect=fail_incoming_copy):
            with self.assertRaises(runner.RecoveryRequiredError):
                self.invoke()
        self.assertTrue(self.active_trial.exists())
        self.assertTrue(self.pointer.exists())
        self.assertFalse(self.archive.exists())
        self.assertFalse(self.result_path.exists())
        self.assertTrue(runner.STOP.is_set())

    def test_result_commit_failure_keeps_archive_and_recovery_pointer(self):
        original_save = runner.save

        def fail_result(path, data):
            if path == self.result_path:
                raise OSError("mock result disk failure")
            return original_save(path, data)
        self.patch("save", side_effect=fail_result)
        with self.assertRaises(runner.RecoveryRequiredError):
            self.invoke()
        self.assertTrue(self.archive.is_dir())
        self.assertTrue(self.pointer.is_file())
        self.assertTrue(self.active_trial.is_dir())
        self.assertFalse(self.result_path.exists())
        runner.STOP.clear()
        calls = self.popen_mock.call_count
        with self.assertRaises(runner.RecoveryRequiredError):
            self.invoke()
        self.assertEqual(self.popen_mock.call_count, calls)

    def test_archive_hash_mismatch_is_critical_and_never_commits_score(self):
        original_copy = runner.shutil.copy2

        def corrupt_incoming(source, destination, **kwargs):
            copied = original_copy(source, destination, **kwargs)
            if any(part.startswith(".incoming-") for part in Path(destination).parts):
                Path(destination).write_text("inert copy corruption")
            return copied
        with mock.patch.object(runner.shutil, "copy2", side_effect=corrupt_incoming):
            with self.assertRaises(runner.CriticalIntegrityError):
                self.invoke()
        self.assertTrue(self.pointer.exists())
        self.assertTrue(self.active_trial.exists())
        self.assertFalse(self.archive.exists())
        self.assertFalse(self.result_path.exists())

    def test_model_reparse_output_is_rejected_before_verifier_or_file_reads(self):
        self.create_script = True
        original_lstat = Path.lstat

        def reparse_stat(path):
            info = original_lstat(path)
            if path.name == "solve.py" and self.active_trial and path.is_relative_to(self.active_trial):
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
            return info

        with mock.patch.object(Path, "lstat", autospec=True, side_effect=reparse_stat):
            with self.assertRaises(runner.CriticalIntegrityError):
                self.invoke()
        self.verifier.assert_not_called()
        self.assertTrue(self.pointer.exists())
        self.assertTrue(self.active_trial.exists())
        self.assertFalse(self.archive.exists())
        self.assertFalse(self.result_path.exists())

    def test_archive_rejects_symlink_and_junction_in_active_temp(self):
        state = {}
        runner.prepare_trial(self.root, self.spec, self.intake, state)
        suspicious = state["parent"] / "tmp/linked-directory"
        suspicious.mkdir()
        original_lstat = Path.lstat
        for attributes, mode in ((0, stat.S_IFLNK), (0x400, stat.S_IFDIR)):
            with self.subTest(attributes=attributes, mode=mode):
                def linked_stat(path):
                    if path == suspicious:
                        return SimpleNamespace(st_mode=mode, st_file_attributes=attributes)
                    return original_lstat(path)
                with mock.patch.object(Path, "lstat", autospec=True, side_effect=linked_stat):
                    with self.assertRaises(runner.CriticalIntegrityError):
                        runner.archive_workspace(self.root, self.spec, state)
                self.assertFalse(self.archive.exists())
                self.assertTrue(self.pointer.exists())
                self.assertTrue(state["workspace"].exists())

    def test_active_guard_drift_halts_before_review_and_preserves_workspace(self):
        self.use_harness()

        def corrupt_guard(proc):
            (self.active_trial.parent / "runner-guards/bin/claude.cmd").write_text("inert tampered guard")
        self.process_hook = corrupt_guard
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.assertEqual(len(self.processes), 1)
        self.assertTrue(self.pointer.exists())
        self.assertTrue(self.active_trial.exists())
        self.assertFalse(self.archive.exists())
        self.assertFalse(self.result_path.exists())

    def test_unexpected_guard_file_is_rejected_without_child_start(self):
        (self.root / "runner-guards/bin/unexpected.exe").write_text("inert extra fixture")
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.popen_mock.assert_not_called()
        self.assertTrue(self.pointer.exists())
        self.assertFalse(self.archive.exists())
        self.assertFalse(self.result_path.exists())

    def test_inherited_environment_root_disclosure_halts_before_child(self):
        with mock.patch.dict(runner.os.environ, {"BAD_FIXTURE": str(self.root / "suite")}):
            with self.assertRaises(runner.CriticalIntegrityError):
                self.invoke()
        self.popen_mock.assert_not_called()
        self.assertTrue(self.pointer.exists())
        self.assertFalse(self.archive.exists())
        self.assertFalse(self.result_path.exists())

    def test_pointer_pid_write_failure_reclaims_child_before_archiving(self):
        original_save = runner.save
        failed = []

        def fail_running_pointer(path, data):
            if path == self.pointer and data.get("state") == "model_running" and not failed:
                failed.append(True)
                raise OSError("mock atomic pointer PID write failure")
            return original_save(path, data)
        self.patch("save", side_effect=fail_running_pointer)
        result = self.invoke()
        self.assertEqual(result["status"], "infrastructure_error")
        self.assertIsNotNone(self.proc.poll())
        self.assertEqual(self.proc.communicate_calls, [])
        self.assertTrue(self.archive.exists())
        self.assertFalse(self.pointer.exists())

    def test_timeout_and_stop_race_keeps_phase_and_top_timeout_consistent(self):
        self.communicate_error = subprocess.TimeoutExpired("FAKE_CLI", 240)
        self.process_hook = lambda proc: setattr(proc, "communicate_hook", runner.STOP.set)
        result = self.invoke()
        self.assertEqual(result["status"], "timeout")
        self.assertTrue(result["timeout"])
        self.assertEqual(result["phases"][0]["status"], "timeout")
        self.assertTrue(result["phases"][0]["timeout"])

    def test_timeout_exit_pointer_failure_preserves_recovery_state_and_halts(self):
        self.communicate_error = subprocess.TimeoutExpired("FAKE_CLI", 240)
        original_save = runner.save

        def fail_exited_pointer(path, data):
            if path == self.pointer and data.get("state") == "model_exited":
                raise OSError("mock exited pointer write failure")
            return original_save(path, data)
        self.patch("save", side_effect=fail_exited_pointer)
        with self.assertRaises(runner.RecoveryRequiredError):
            self.invoke()
        phases = runner.saved_phases(self.root, self.spec)
        self.assertEqual(len(phases), 1)
        self.assertTrue(phases[0]["timeout"])
        self.assertEqual(phases[0]["status"], "timeout")
        self.assertEqual(phases[0]["exit_code"], -9)
        self.assertEqual(runner.ACTIVE, {})
        self.assertTrue(runner.STOP.is_set())
        self.assertTrue(self.active_trial.is_dir())
        self.assertEqual(json.loads(self.pointer.read_text())["state"], "model_running")
        self.assertFalse(self.archive.exists())
        self.assertFalse(self.result_path.exists())
        with self.assertRaises(runner.RecoveryRequiredError):
            runner.assert_no_partial_trials(self.root, [self.spec])

    def test_error_after_timeout_reclaim_keeps_phase_and_top_timeout(self):
        self.communicate_error = subprocess.TimeoutExpired("FAKE_CLI", 240)
        original_reclaim = runner.reclaim_child

        def reclaim_then_fail(proc):
            original_reclaim(proc)
            raise OSError("mock post-reclaim bookkeeping failure")
        self.patch("reclaim_child", side_effect=reclaim_then_fail)
        result = self.invoke()
        self.assertTrue(result["timeout"])
        self.assertEqual(result["status"], "timeout")
        self.assertTrue(result["phases"][0]["timeout"])
        self.assertEqual(result["phases"][0]["status"], "timeout")
        self.assertEqual(result, self.stored())
        self.assertEqual(runner.ACTIVE, {})
        self.assertFalse(result["correct"])

    def test_prelaunch_error_with_stop_has_phase_free_infrastructure_result(self):
        def fail_command(*args, **kwargs):
            runner.STOP.set()
            raise OSError("mock prelaunch command failure")
        self.patch("phase_command", side_effect=fail_command)
        result = self.invoke()
        self.assertEqual(result["phases"], [])
        self.assertEqual(result["status"], "infrastructure_error")
        self.assertFalse(result["timeout"])
        self.assertEqual(result["model_calls"], 0)
        self.assertTrue(runner.STOP.is_set())
        self.assertEqual(result, self.stored())
        self.popen_mock.assert_not_called()

    def test_stop_during_first_phase_setup_does_not_emit_phase_free_cancelled(self):
        original_command = runner.phase_command
        clock = [0.0]

        def stop_before_launch(*args, **kwargs):
            command = original_command(*args, **kwargs)
            clock[0] = 250.0
            runner.STOP.set()
            return command
        self.patch("phase_command", side_effect=stop_before_launch)
        with mock.patch.object(runner.time, "monotonic", side_effect=lambda: clock[0]):
            result = self.invoke()
        self.assertEqual(result["phases"], [])
        self.assertEqual(result["status"], "infrastructure_error")
        self.assertFalse(result["timeout"])
        self.assertEqual(result["model_calls"], 0)
        self.popen_mock.assert_not_called()

    def test_added_empty_input_directory_fails_originals_integrity(self):
        def add_directory_during_trial(proc):
            (self.work.parent / "untrusted/unexpected-empty-directory").mkdir()

        self.process_hook = add_directory_during_trial
        result = self.invoke()
        self.assertTrue(result["correct"], "Integrity and candidate correctness are separate measurements")
        self.assertFalse(result["originals_unchanged"])
        self.assertFalse(self.stored()["originals_unchanged"])

    def test_timeout_reclaims_child_and_rejects_even_completed_candidate(self):
        self.communicate_error = subprocess.TimeoutExpired("FAKE_CLI", 60)
        result = self.invoke()
        self.assertFalse(result["correct"])
        self.assertTrue(result["timeout"])
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(self.kill_commands(), [["taskkill", "/PID", "424242", "/T", "/F"]])
        self.assertEqual(self.proc.wait_calls, [30])
        self.assertEqual(runner.ACTIVE, {})

    def test_post_timeout_artifact_error_preserves_timeout_in_fallback(self):
        self.communicate_error = subprocess.TimeoutExpired("FAKE_CLI", 240)
        original_iterdir = Path.iterdir
        failed = []

        def fail_final_input_inspection(path):
            if path == self.work.parent / "untrusted" and not failed:
                failed.append(True)
                raise OSError("mock post-timeout artifact inspection failure")
            return original_iterdir(path)
        with mock.patch.object(Path, "iterdir", autospec=True, side_effect=fail_final_input_inspection):
            result = self.invoke()
        self.assertEqual(result["status"], "timeout")
        self.assertTrue(result["timeout"])
        self.assertTrue(result["time_censored"])
        self.assertTrue(result["phases"][0]["timeout"])
        self.assertFalse(result["correct"])
        self.assertIn("post-timeout", result["error"])
        self.assertEqual(result["model_calls"], 1)
        self.assertEqual(runner.ACTIVE, {})

    def test_post_cancel_artifact_error_preserves_cancelled_in_fallback(self):
        self.process_hook = lambda proc: setattr(proc, "communicate_hook", runner.STOP.set)
        original_iterdir = Path.iterdir
        failed = []

        def fail_final_input_inspection(path):
            if path == self.work.parent / "untrusted" and not failed:
                failed.append(True)
                raise OSError("mock post-cancel artifact inspection failure")
            return original_iterdir(path)
        with mock.patch.object(Path, "iterdir", autospec=True, side_effect=fail_final_input_inspection):
            result = self.invoke()
        self.assertEqual(result["status"], "cancelled")
        self.assertFalse(result["timeout"])
        self.assertFalse(result["correct"])
        self.assertEqual(result["phases"][0]["status"], "cancelled")

    def test_unfinished_turn_candidate_is_not_success(self):
        self.log = self.completed_log(completed=False)
        result = self.invoke()
        self.assertEqual(result["final"], CANDIDATE)
        self.assertFalse(result["turn_completed"])
        self.assertFalse(result["correct"])
        self.assertEqual(result["status"], "infrastructure_error")

    def test_model_nonzero_exit_cannot_be_success(self):
        self.exit_code = 7
        result = self.invoke()
        self.assertFalse(result["correct"])
        self.assertEqual(result["exit_code"], 7)
        self.assertEqual(result["status"], "infrastructure_error")

    def test_verifier_process_nonzero_rejects_both_stdout_candidates(self):
        self.verifier_result(process_code=8)
        result = self.invoke()
        self.assertTrue(result["correct"])
        self.assertFalse(result["verification"]["same_instance"])
        self.assertFalse(result["verification"]["new_instance"])

    def test_script_nonzero_exit_rejects_same_and_new_reproduction(self):
        self.verifier_result(same_code=1, new_code=2)
        result = self.invoke()
        self.assertTrue(result["correct"])
        self.assertFalse(result["verification"]["same_instance"])
        self.assertFalse(result["verification"]["new_instance"])

    def test_verifier_timeout_keeps_completed_model_result(self):
        self.create_script = True
        self.verifier.side_effect = subprocess.TimeoutExpired("FAKE_VERIFIER", 50)
        result = self.invoke()
        self.assertTrue(result["correct"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["verification"]["status"], "verification_infrastructure_error")
        self.assertTrue(self.stored()["correct"])

    def test_verifier_malformed_json_keeps_completed_model_result(self):
        self.verifier_result()
        self.verifier.return_value.stdout = "truncated {"
        result = self.invoke()
        self.assertTrue(result["correct"])
        self.assertEqual(result["verification"]["status"], "verification_infrastructure_error")

    def test_verifier_wrong_json_shape_keeps_completed_model_result(self):
        self.verifier_result()
        self.verifier.return_value.stdout = "[]"
        result = self.invoke()
        self.assertTrue(result["correct"], "Verifier schema errors must not erase a completed model answer")
        self.assertEqual(result["verification"]["status"], "verification_infrastructure_error")

    def test_process_handle_record_failure_reclaims_child_and_records_infra(self):
        original_save = runner.save

        def fail_process_record(path, data):
            if path.name == "process.json":
                raise OSError("mock process handle record failure")
            return original_save(path, data)

        self.patch("save", side_effect=fail_process_record)
        result = self.invoke()
        self.assertEqual(result["status"], "infrastructure_error")
        self.assertIn("handle record failure", result["error"])
        self.assertEqual(self.kill_commands(), [["taskkill", "/PID", "424242", "/T", "/F"]])
        self.assertEqual(self.proc.wait_calls, [30])
        self.assertEqual(runner.ACTIVE, {})
        self.assertFalse(self.stored()["correct"])

    def test_communicate_error_reclaims_still_live_child(self):
        self.communicate_error = OSError("mock broken stdin pipe")
        result = self.invoke()
        self.assertEqual(result["status"], "infrastructure_error")
        self.assertEqual(self.kill_commands(), [["taskkill", "/PID", "424242", "/T", "/F"]],
                         "A communicate exception must not detach a still-live child")
        self.assertIsNotNone(self.proc.poll())
        self.assertEqual(runner.ACTIVE, {})

    def test_cleanup_exception_retains_live_handle_and_halts(self):
        self.communicate_error = OSError("mock broken stdin pipe")
        cleanup = self.patch("stop_child", side_effect=subprocess.TimeoutExpired("FAKE_TASKKILL", 30))
        with self.assertRaises(runner.ChildCleanupError):
            self.invoke()
        cleanup.assert_called_once_with(self.proc)
        self.assertIsNone(self.proc.poll(), "The fake child intentionally remains live")
        self.assertIs(runner.ACTIVE.get(self.spec["id"]), self.proc)
        self.assertFalse(self.result_path.exists(), "An unreaped child must not become a terminal result")
        self.assertTrue(runner.STOP.is_set())
        self.assertTrue(self.active_trial.exists())
        self.assertTrue(self.pointer.exists())
        self.assertFalse(self.archive.exists())
        process_record = self.root / "logs" / self.spec["id"] / "phases/codex_solve/process.json"
        self.assertEqual(json.loads(process_record.read_text())["pid"], self.proc.pid)

    def test_unconfirmed_cleanup_retains_live_handle_and_halts(self):
        self.communicate_error = OSError("mock broken stdin pipe")
        cleanup = self.patch("stop_child", return_value=None)
        with self.assertRaisesRegex(RuntimeError, "termination not confirmed"):
            self.invoke()
        cleanup.assert_called_once_with(self.proc)
        self.assertIsNone(self.proc.poll())
        self.assertIs(runner.ACTIVE.get(self.spec["id"]), self.proc)
        self.assertFalse(self.result_path.exists())

    def test_timeout_cleanup_failure_is_not_retried_or_made_terminal(self):
        self.communicate_error = subprocess.TimeoutExpired("FAKE_CLI", 240)
        cleanup = self.patch("stop_child", side_effect=OSError("mock kill failure"))
        with self.assertRaises(runner.ChildCleanupError):
            self.invoke()
        cleanup.assert_called_once_with(self.proc)
        self.assertIs(runner.ACTIVE[self.spec["id"]], self.proc)
        self.assertTrue(runner.STOP.is_set())
        self.assertFalse(self.result_path.exists())

    def test_popen_failure_is_persisted_as_infrastructure_failure(self):
        self.popen_mock.side_effect = OSError("mock executable missing")
        result = self.invoke()
        self.assertEqual(result["status"], "infrastructure_error")
        self.assertEqual(result["final"], "")
        self.assertTrue(result["originals_unchanged"])
        self.assertIn("executable missing", self.stored()["error"])
        self.assertEqual(self.kill_commands(), [])

    def test_popen_failure_after_input_mutation_records_originals_changed(self):
        def mutate_then_fail(command, **kwargs):
            challenge = (Path(kwargs["cwd"]) / "events" / "local-benchmark" / "challenges"
                         / self.spec["instance"])
            (challenge / "untrusted" / "fixture.txt").write_text("changed before mock launch failure")
            raise OSError("mock executable missing after mutation")

        self.popen_mock.side_effect = mutate_then_fail
        result = self.invoke()
        self.assertEqual(result["status"], "infrastructure_error")
        self.assertFalse(result["originals_unchanged"])
        self.assertFalse(self.stored()["originals_unchanged"])

    def test_popen_failure_signed_archive_round_trips_through_summary(self):
        old_instance = self.root / "suite" / self.spec["instance"]
        self.spec.update(id="codex_raw-layered-r1", instance="layered-r1", task="layered")
        new_instance = self.root / "suite" / self.spec["instance"]
        old_instance.rename(new_instance)
        self.input = new_instance / "untrusted"
        input_hashes = {"fixture.txt": hashlib.sha256(
            (self.input / "fixture.txt").read_bytes()).hexdigest()}
        self.key = {self.spec["instance"]: {"flag_sha256": DIGEST, "hashes": input_hashes}}
        (self.root / "suite" / "answer-key.json").write_text(
            json.dumps(self.key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        commitments = unseen_fixture(self.spec["instance"])
        self.args.artifact_hashes["suite_hashes"] = runner.tree_hashes(self.root / "suite")
        self.args.artifact_hashes["unseen_commitments"] = commitments
        self.args.artifact_hashes["unseen_commitments_sha256"] = runner.tree_digest(commitments)
        self.popen_mock.side_effect = OSError("mock executable missing")
        result = self.invoke()
        self.assertTrue(result["originals_unchanged"])

        protocol = {
            "protocol_version": runner.PROTOCOL_VERSION,
            "suite_version": runner.SUITE_VERSION,
            "master_seed_sha256": self.args.artifact_hashes["master_seed_sha256"],
            "unseen_commitments": commitments,
            "unseen_commitments_sha256": runner.tree_digest(commitments),
            "suite_hashes": self.args.artifact_hashes["suite_hashes"],
            "benchmark_code_hashes": runner.benchmark_code_hashes(),
            "arms": list(runner.ARMS), "phase_plans": runner.phase_protocol(),
            "provider_execution": json.loads(json.dumps(runner.PROVIDER_EXECUTION)),
            "timeout": runner.TOTAL_BUDGET_SECONDS, "workers": 1,
            "tasks": ["layered"], "repeats": 1,
            "claude_model": self.args.claude_model, "codex_model": self.args.codex_model,
            "specs": runner.build_specs(["layered"], 1),
        }
        protocol["protocol_hmac_sha256"] = runner.protocol_hmac_sha256(self.root, protocol)
        loaded = summary.load_results(
            self.root, protocol, commitment_regenerator=lambda _root, _protocol: commitments)
        self.assertEqual([row["id"] for row in loaded], [self.spec["id"]])
        self.assertTrue(loaded[0]["originals_unchanged"])

    def test_saved_result_resumes_without_any_execution(self):
        saved = self.write_signed_result()
        before = self.result_path.read_bytes()
        self.assertEqual(self.invoke(), saved)
        self.assertEqual(self.result_path.read_bytes(), before)
        self.popen_mock.assert_not_called()
        self.run.assert_not_called()
        self.verifier.assert_not_called()
        runner.tempfile.mkdtemp.assert_not_called()

    def test_saved_result_symlink_shape_is_rejected_without_execution(self):
        self.write_signed_result()
        original_lstat = Path.lstat

        def report_result_as_symlink(path):
            if path == self.result_path:
                return SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)
            return original_lstat(path)

        with mock.patch.object(Path, "lstat", new=report_result_as_symlink):
            with self.assertRaises(runner.CriticalIntegrityError):
                self.invoke()
        self.popen_mock.assert_not_called()
        self.verifier.assert_not_called()
        runner.tempfile.mkdtemp.assert_not_called()

    def test_forged_precreated_result_is_rejected_without_execution(self):
        runner.save(self.result_path, {**self.spec, "status": "completed", "correct": True})
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.popen_mock.assert_not_called()
        self.verifier.assert_not_called()
        runner.tempfile.mkdtemp.assert_not_called()

    def test_saved_result_hmac_tamper_is_rejected_without_execution(self):
        saved = self.write_signed_result()
        saved["correct"] = False
        runner.save(self.result_path, saved)
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.popen_mock.assert_not_called()
        self.verifier.assert_not_called()

    def test_saved_result_archive_tamper_is_rejected_without_execution(self):
        self.write_signed_result()
        (self.archive / "inert-archive.txt").write_text("tampered archive fixture\n")
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.popen_mock.assert_not_called()
        self.verifier.assert_not_called()

    def test_resigned_result_with_wrong_spec_is_rejected_without_execution(self):
        saved = self.write_signed_result(arm="claude_raw")
        saved["result_hmac_sha256"] = runner.result_hmac_sha256(self.root, saved)
        runner.save(self.result_path, saved)
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.popen_mock.assert_not_called()
        self.verifier.assert_not_called()

    def test_resigned_result_with_json_type_changed_spec_is_rejected_without_execution(self):
        self.write_signed_result(repeat=True)
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.popen_mock.assert_not_called()
        self.verifier.assert_not_called()

    def test_resigned_result_with_wrong_archive_path_is_rejected_without_execution(self):
        self.write_signed_result(archive_path="trials/other-trial")
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.popen_mock.assert_not_called()
        self.verifier.assert_not_called()

    def test_existing_partial_trial_is_not_restarted_or_overwritten(self):
        self.trial.mkdir(parents=True)
        marker = self.trial / "unfinished.txt"
        marker.write_text("live-or-terminal status has not been established")
        logs = self.root / "logs" / self.spec["id"]
        logs.mkdir(parents=True)
        process = logs / "process.json"
        process.write_text('{"pid":424242,"state":"unknown"}')
        before = process.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "process inspection"):
            self.invoke()
        self.popen_mock.assert_not_called()
        self.run.assert_not_called()
        self.assertFalse(self.result_path.exists())
        self.assertEqual(process.read_bytes(), before)
        self.assertTrue(marker.exists())

    def test_existing_live_trial_handle_is_not_claimed_by_duplicate_invocation(self):
        self.trial.mkdir(parents=True)
        live = FakeProcess(io.StringIO(), "")
        runner.ACTIVE[self.spec["id"]] = live
        with self.assertRaisesRegex(RuntimeError, "process inspection"):
            self.invoke()
        self.assertIs(runner.ACTIVE[self.spec["id"]], live)
        self.assertIsNone(live.poll())
        self.assertEqual(self.kill_commands(), [])
        self.popen_mock.assert_not_called()

    def test_stop_before_prepare_does_not_create_trial_or_launch(self):
        runner.STOP.set()
        self.assertIsNone(self.invoke())
        self.assertFalse(self.trial.exists())
        self.popen_mock.assert_not_called()

    def test_stop_during_prepare_prevents_late_process_launch(self):
        original_prepare = runner.prepare_trial

        def prepare_then_stop(*args):
            prepared = original_prepare(*args)
            runner.STOP.set()
            return prepared

        self.patch("prepare_trial", side_effect=prepare_then_stop)
        self.assertIsNone(self.invoke())
        self.popen_mock.assert_not_called()
        self.assertEqual(runner.ACTIVE, {})

    def test_stop_during_popen_cannot_miss_active_registration(self):
        stop_requested = threading.Event()
        child_reclaimed = threading.Event()
        coordinator_errors = []

        def coordinator():
            try:
                runner.STOP.set()
                stop_requested.set()
                with runner.ACTIVE_LOCK:
                    children = list(runner.ACTIVE.values())
                if not children:
                    raise AssertionError("Cancellation missed a newly-created child")
                for child in children:
                    runner.stop_child(child)
            except BaseException as error:
                coordinator_errors.append(error)
            finally:
                child_reclaimed.set()

        def during_popen(proc):
            self.coordinator = threading.Thread(target=coordinator, daemon=True)
            self.coordinator.start()
            if not stop_requested.wait(2):
                raise AssertionError("Cancellation coordinator did not start")

            def wait_for_reclaim():
                if not child_reclaimed.wait(2):
                    raise AssertionError("Cancellation coordinator could not reclaim child")
            proc.communicate_hook = wait_for_reclaim

        self.process_hook = during_popen
        result = self.invoke()
        self.coordinator.join(timeout=2)
        self.assertFalse(self.coordinator.is_alive())
        self.assertEqual(coordinator_errors, [])
        self.assertFalse(result["correct"])
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(self.proc.wait_calls, [30])
        self.assertEqual(runner.ACTIVE, {})

    def test_raw_arms_never_copy_project_snapshot_or_answer_key(self):
        self.use_harness()
        (self.root / "suite/answer-key.json").write_text(json.dumps(self.key))
        for arm, provider in [("claude_raw", "claude"), ("codex_raw", "codex")]:
            spec = {**self.spec, "id": arm + "-mock-r1", "arm": arm,
                    "provider": provider, "condition": "raw"}
            trial, challenge = runner.prepare_trial(self.root, spec, self.intake)
            for absent in ("AGENTS.md", "CLAUDE.md", ".claude", ".agents", ".codex"):
                self.assertFalse((trial / absent).exists(), (arm, absent))
            self.assertEqual((challenge / "untrusted/fixture.txt").read_bytes(),
                             (self.input / "fixture.txt").read_bytes())
            self.assertEqual(list(trial.rglob("answer-key.json")), [])
            self.assertNotIn(DIGEST, (trial / "events/local-benchmark/NOTES.md").read_text())
        self.popen_mock.assert_not_called()

    def test_harness_runs_fixed_order_with_read_only_review_and_separate_logs(self):
        self.use_harness()
        reviewer_text = "Review: check the parser boundary."

        def check_handoff(proc):
            if len(self.processes) == 3:
                self.assertEqual((self.work / "codex-review.md").read_text(), reviewer_text + "\n")
        self.process_hook = check_handoff
        result = self.invoke()
        self.assertTrue(result["correct"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual([p["name"] for p in result["phases"]],
                         ["claude_solve", "codex_review", "claude_finalize"])
        commands = [call.args[0] for call in self.popen_mock.call_args_list]
        self.assertEqual([c[0] for c in commands], [self.cli_paths[name]
                         for name in ["FAKE_CLAUDE", "FAKE_CODEX", "FAKE_CLAUDE"]])
        self.assertEqual(commands[1][commands[1].index("--sandbox") + 1], "danger-full-access")
        self.assertTrue(result["phases"][1]["read_only"])
        for feature in ("apps", "multi_agent", "multi_agent_v2", "hooks", "plugins", "remote_plugin"):
            self.assertIn(f"features.{feature}=false", commands[1])
        self.assertNotIn("features.skip_host_skill_discovery=true", commands[1])
        self.assertNotIn("--disable-slash-commands", commands[0])
        self.assertNotIn("--safe-mode", commands[0])
        self.assertNotIn("--safe-mode", commands[2])
        self.assertTrue((self.trial / "AGENTS.md").is_file())
        self.assertTrue((self.trial / ".claude/skills/fixture/SKILL.md").is_file())
        self.assertEqual([p["cap_seconds"] for p in result["phases"]], [120, 60, 60])
        self.assertEqual([p["requested_model"] for p in result["phases"]],
                         ["fake-claude-model", "fake-codex-model", "fake-claude-model"])
        self.assertEqual(result["tool_calls"], 2)
        self.assertEqual(result["usage"], {}, "Mixed provider accounting must use phase usage")
        self.assertEqual(result["model_calls"], 3)
        self.assertGreaterEqual(result["total_wall_seconds"], 0)
        for index, phase in enumerate(result["phases"]):
            logs = self.root / phase["log_dir"]
            self.assertTrue((logs / "stdout.jsonl").read_text())
            self.assertIn(f"phase {index + 1}", (logs / "stderr.txt").read_text())
            self.assertEqual(json.loads((logs / "result.json").read_text()), phase)
            prompt = (logs / "prompt.txt").read_text()
            self.assertNotIn(DIGEST, prompt, "The expected answer digest is never a prompt input")
            self.assertEqual(phase["exit_code"], 0)
            self.assertTrue(phase["process_started"])
            self.assertTrue(phase["usage"])
        self.assertIn("codex-review.md", self.processes[2].communicate_calls[0][0])
        self.assertEqual(runner.ACTIVE, {})

    def assert_review_mutation_stops(self, mutate, *, review_error=None):
        self.use_harness()
        if review_error is not None:
            self.phase_configs[1]["communicate_error"] = review_error

        def change_only_during_review(proc):
            if len(self.processes) == 2:
                mutate()
        self.process_hook = change_only_during_review
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.assertEqual(len(self.processes), 2, "Mutation must prevent Claude finalization")
        self.assertTrue(runner.STOP.is_set())
        self.assertEqual(runner.ACTIVE, {})
        self.assertTrue(self.pointer.exists())
        self.assertTrue(self.active_trial.exists())
        self.assertFalse(self.archive.exists())
        self.assertFalse(self.result_path.exists())
        self.assertFalse((self.work / "codex-review.md").exists(), "Runner handoff follows a successful tree check")
        self.verifier.assert_not_called()
        review = runner.saved_phases(self.root, self.spec)[1]
        evidence = review["review_integrity"]
        self.assertEqual(set(evidence), {"before_digest", "after_digest", "verified", "enforcement"})
        self.assertRegex(evidence["before_digest"], r"^[0-9a-f]{64}$")
        self.assertFalse(evidence["verified"])
        if evidence["after_digest"] is not None:
            self.assertRegex(evidence["after_digest"], r"^[0-9a-f]{64}$")
            self.assertNotEqual(evidence["before_digest"], evidence["after_digest"])
        self.assertEqual(evidence["enforcement"], "trial-tree-hashes-before-and-after")

    def test_review_file_creation_is_critical_before_handoff(self):
        self.assert_review_mutation_stops(lambda: (self.work / "unauthorized.txt").write_text("inert review mutation"))

    def test_review_file_deletion_outside_work_is_critical(self):
        self.assert_review_mutation_stops(lambda: (self.trial / "AGENTS.md").unlink())

    def test_review_file_modification_outside_work_is_critical(self):
        self.assert_review_mutation_stops(lambda: (self.trial / "AGENTS.md").write_text("inert changed instructions"))

    def test_review_empty_directory_creation_is_critical(self):
        self.assert_review_mutation_stops(lambda: (self.work / "unexpected-empty").mkdir())

    def test_review_link_is_critical_without_following_it(self):
        original_lstat = Path.lstat

        def link_stat(path):
            if path.name == "review-link" and self.active_trial and path.is_relative_to(self.active_trial):
                return SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)
            return original_lstat(path)
        with mock.patch.object(Path, "lstat", autospec=True, side_effect=link_stat):
            self.assert_review_mutation_stops(lambda: (self.work / "review-link").write_text("inert link fixture"))

    def test_review_pipe_error_still_checks_mutation_after_reaping_child(self):
        self.assert_review_mutation_stops(lambda: (self.work / "unexpected.txt").write_text("inert mutation"),
                                         review_error=OSError("mock review pipe failure"))
        self.assertEqual(self.processes[1].poll(), -9)

    def test_review_timeout_cannot_hide_trial_mutation(self):
        self.assert_review_mutation_stops(lambda: (self.work / "unexpected.txt").write_text("inert mutation"),
                                         review_error=subprocess.TimeoutExpired("FAKE_CLI", 60))
        self.assertEqual(self.processes[1].poll(), -9)

    def test_unmodified_review_passes_tree_guard_before_runner_handoff(self):
        self.use_harness()
        observed = []
        original_check = runner.assert_review_integrity

        def observe_check(state, **kwargs):
            if state.get("review_hashes") is not None:
                self.assertFalse((self.work / "codex-review.md").exists())
                self.assertEqual(runner.tree_hashes(state["workspace"]), state["review_hashes"])
                observed.append(runner.tree_digest(state["review_hashes"]))
            return original_check(state, **kwargs)
        self.patch("assert_review_integrity", side_effect=observe_check)
        result = self.invoke()
        self.assertEqual(len(observed), 1)
        self.assertEqual(len(self.processes), 3)
        self.assertTrue(result["correct"])
        self.assertTrue((self.work / "codex-review.md").exists())
        self.assertTrue(self.archive.exists())
        evidence = result["review_integrity"]
        self.assertEqual(evidence, {"before_digest": observed[0], "after_digest": observed[0],
                                   "verified": True, "enforcement": "trial-tree-hashes-before-and-after"})
        self.assertRegex(observed[0], r"^[0-9a-f]{64}$")
        self.assertEqual(result["phases"][1]["review_integrity"], evidence)
        self.assertEqual(runner.saved_phases(self.root, self.spec)[1]["review_integrity"], evidence)
        self.assertEqual(self.stored()["review_integrity"], evidence)
        self.assertNotIn(str(self.active_trial), json.dumps(evidence))
        self.assertNotIn("fixture.txt", json.dumps(evidence))

    def test_unmodified_review_timeout_has_no_verified_success_evidence(self):
        self.use_harness()
        self.phase_configs[1]["communicate_error"] = subprocess.TimeoutExpired("FAKE_CLI", 60)
        result = self.invoke()
        self.assertEqual(len(self.processes), 2)
        self.assertEqual(result["status"], "timeout")
        self.assertFalse(result["review_integrity"]["verified"])
        self.assertEqual(result["review_integrity"]["before_digest"], result["review_integrity"]["after_digest"])
        self.assertEqual(runner.saved_phases(self.root, self.spec)[1]["review_integrity"], result["review_integrity"])
        self.assertEqual(self.stored()["review_integrity"], result["review_integrity"])
        self.assertFalse((self.work / "codex-review.md").exists())

    def test_unmodified_review_pipe_error_has_no_verified_success_evidence(self):
        self.use_harness()
        self.phase_configs[1]["communicate_error"] = OSError("mock review pipe failure")
        result = self.invoke()
        self.assertEqual(len(self.processes), 2)
        self.assertEqual(result["status"], "infrastructure_error")
        self.assertFalse(result["review_integrity"]["verified"])
        self.assertEqual(result["review_integrity"]["before_digest"], result["review_integrity"]["after_digest"])
        self.assertEqual(runner.saved_phases(self.root, self.spec)[1]["review_integrity"], result["review_integrity"])
        self.assertEqual(self.stored()["review_integrity"], result["review_integrity"])
        self.assertEqual(runner.ACTIVE, {})
        self.assertFalse((self.work / "codex-review.md").exists())

    def test_raw_codex_may_write_trial_with_full_wsl_access(self):
        self.process_hook = lambda proc: (self.work / "analysis.txt").write_text("inert raw output")
        result = self.invoke()
        self.assertTrue(result["correct"])
        self.assertEqual((self.work / "analysis.txt").read_text(), "inert raw output")
        self.assertEqual(result["status"], "completed")

    def test_raw_claude_uses_full_budget_and_disables_project_skills(self):
        self.spec.update(id="claude_raw-mock-r1", arm="claude_raw", provider="claude")
        self.log = self.claude_log()
        with mock.patch.object(runner.time, "monotonic", return_value=10.0):
            result = self.invoke()
        self.assertTrue(result["correct"])
        self.assertEqual(len(self.processes), 1)
        self.assertEqual(self.proc.communicate_calls[0][1], 240)
        self.assertIn("--disable-slash-commands", self.popen_mock.call_args.args[0])
        self.assertIn("--safe-mode", self.popen_mock.call_args.args[0])
        command = self.popen_mock.call_args.args[0]
        self.assertEqual(command[command.index("--permission-mode") + 1], "dontAsk")
        self.assertEqual(command[command.index("--tools") + 1], "Bash,Read,Write,Edit,Glob,Grep,Skill")
        self.assertEqual(command[command.index("--allowedTools") + 1], "Bash,Read,Write,Edit,Glob,Grep,Skill")
        self.assertEqual(result["phases"][0]["name"], "claude_solve")
        self.assertNotIn("Fixed collaboration phase", self.proc.communicate_calls[0][0])
        self.assertEqual(result["phases"][0]["cap_seconds"], 240)
        self.assertFalse((self.trial / "AGENTS.md").exists())

    def test_harness_only_final_claude_candidate_can_be_correct(self):
        self.use_harness()
        self.phase_configs[1]["log"] = self.completed_log(final="Reviewer proposes " + CANDIDATE)
        self.phase_configs[2]["log"] = self.claude_log(final="unsolved")
        result = self.invoke()
        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["correct"])
        self.assertEqual(result["final"], "unsolved")
        self.assertIn(CANDIDATE, (self.work / "codex-review.md").read_text())

    def test_finalization_can_correct_primary_unsolved_response(self):
        self.use_harness()
        self.phase_configs[0]["log"] = self.claude_log(final="unsolved")
        result = self.invoke()
        self.assertTrue(result["correct"])
        self.assertEqual(result["final"], CANDIDATE)

    def test_failed_review_aborts_finalization_and_cannot_reuse_primary_flag(self):
        self.use_harness()
        self.phase_configs[1]["exit_code"] = 7
        result = self.invoke()
        self.assertFalse(result["correct"])
        self.assertEqual(result["status"], "infrastructure_error")
        self.assertFalse(result["timeout"])
        self.assertEqual(result["final"], "")
        self.assertEqual(len(self.processes), 2)
        self.assertEqual(result["phases"][1]["exit_code"], 7)
        self.assertFalse((self.work / "codex-review.md").exists())

    def test_unfinished_review_aborts_finalization(self):
        self.use_harness()
        self.phase_configs[1]["log"] = self.completed_log(completed=False)
        result = self.invoke()
        self.assertFalse(result["correct"])
        self.assertEqual(result["status"], "infrastructure_error")
        self.assertEqual(len(self.processes), 2)

    def test_harness_primary_timeout_aborts_remaining_phases(self):
        self.use_harness()
        self.phase_configs[0]["communicate_error"] = subprocess.TimeoutExpired("FAKE_CLAUDE", 120)
        result = self.invoke()
        self.assertFalse(result["correct"])
        self.assertTrue(result["timeout"])
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(len(self.processes), 1)
        self.assertEqual(self.proc.wait_calls, [30])
        self.assertEqual(runner.ACTIVE, {})

    def test_shared_deadline_counts_phase_transition_overhead(self):
        self.use_harness()
        clock = [0.0]
        durations = [110, 50, 49]

        def advance_clock(proc):
            duration = durations[len(self.processes) - 1]
            proc.communicate_hook = lambda: clock.__setitem__(0, clock[0] + duration)
        self.process_hook = advance_clock
        original_phase = runner.execute_phase

        def execute_with_transition_cost(*args, **kwargs):
            phase = original_phase(*args, **kwargs)
            if phase and phase["name"] == "claude_solve":
                clock[0] += 30
            return phase
        self.patch("execute_phase", side_effect=execute_with_transition_cost)
        with mock.patch.object(runner.time, "monotonic", side_effect=lambda: clock[0]):
            result = self.invoke()
        self.assertEqual([p.communicate_calls[0][1] for p in self.processes], [120, 60, 50])
        self.assertEqual(result["total_wall_seconds"], 239)
        self.assertTrue(result["correct"])

    def test_no_next_child_starts_after_shared_budget_is_consumed(self):
        self.use_harness()
        clock = [0.0]
        original_phase = runner.execute_phase

        def spend_remaining_budget(*args, **kwargs):
            phase = original_phase(*args, **kwargs)
            if phase and phase["name"] == "claude_solve":
                clock[0] = 240.0
            return phase
        self.patch("execute_phase", side_effect=spend_remaining_budget)
        with mock.patch.object(runner.time, "monotonic", side_effect=lambda: clock[0]):
            result = self.invoke()
        self.assertEqual(len(self.processes), 1)
        self.assertEqual(result["phases"][-1]["budget_seconds"], 0)
        self.assertFalse(result["phases"][-1]["process_started"])
        self.assertEqual(result["model_calls"], 1)
        self.assertTrue(result["timeout"])
        self.assertEqual(result["status"], "timeout")
        self.assertFalse(result["correct"])

    def test_late_successful_exit_still_exceeds_phase_cap(self):
        self.use_harness()
        clock = [0.0]
        self.process_hook = lambda proc: setattr(proc, "communicate_hook", lambda: clock.__setitem__(0, 121.0))
        with mock.patch.object(runner.time, "monotonic", side_effect=lambda: clock[0]):
            result = self.invoke()
        self.assertEqual(len(self.processes), 1)
        self.assertTrue(result["timeout"])
        self.assertFalse(result["correct"])

    def test_stop_between_phases_prevents_review_launch(self):
        self.use_harness()
        original_phase = runner.execute_phase

        def stop_after_primary(*args, **kwargs):
            phase = original_phase(*args, **kwargs)
            runner.STOP.set()
            return phase
        self.patch("execute_phase", side_effect=stop_after_primary)
        result = self.invoke()
        self.assertEqual(len(self.processes), 1)
        self.assertEqual(result["status"], "cancelled")
        self.assertFalse(result["correct"])
        self.assertEqual(runner.ACTIVE, {})

    def test_finalization_pipe_failure_preserves_earlier_phase_usage(self):
        self.use_harness()
        self.phase_configs[2]["communicate_error"] = OSError("mock finalization pipe failure")
        result = self.invoke()
        self.assertEqual(result["status"], "infrastructure_error")
        self.assertFalse(result["correct"])
        self.assertEqual(len(result["phases"]), 3)
        self.assertEqual([p["status"] for p in result["phases"]],
                         ["completed", "completed", "infrastructure_error"])
        self.assertEqual(result["phases"][0]["usage"]["output_tokens"], 7)
        self.assertEqual(result["phases"][1]["usage"]["output_tokens"], 4)
        self.assertEqual(result["phases"][2]["exit_code"], -9)
        self.assertEqual(runner.ACTIVE, {})

    def test_verifier_runs_once_after_all_harness_children_exit(self):
        self.use_harness()
        self.verifier_result()
        original_response = self.verifier.return_value

        def verify_after_exit(*args, **kwargs):
            self.assertEqual(len(self.processes), 3)
            self.assertTrue(all(proc.poll() == 0 for proc in self.processes))
            self.assertEqual(runner.ACTIVE, {})
            self.assertTrue((self.work / "codex-review.md").is_file())
            return original_response
        self.verifier.side_effect = verify_after_exit
        result = self.invoke()
        self.verifier.assert_called_once()
        self.assertTrue(result["correct"])
        self.assertTrue(result["verification"]["same_instance"])

    def test_all_child_provider_environments_prepend_denies_without_mutating_parent(self):
        self.use_harness()
        parent_path = runner.os.environ.get("PATH", "")
        with mock.patch.dict(runner.os.environ, {"CLAUDECODE": "parent-marker", "WSLENV": "KEEP/u:BASH_ENV/u"}):
            result = self.invoke()
            self.assertEqual(runner.os.environ.get("PATH", ""), parent_path)
            self.assertEqual(runner.os.environ["CLAUDECODE"], "parent-marker")
            self.assertEqual(runner.os.environ["WSLENV"], "KEEP/u:BASH_ENV/u")
        self.assertTrue(result["correct"])
        guard_dir = self.active_trial.parent / "runner-guards/bin"
        for call in self.popen_mock.call_args_list:
            environment = call.kwargs["env"]
            self.assertEqual(environment["PATH"].split(runner.os.pathsep)[0], str(guard_dir))
            self.assertEqual(environment["BASH_ENV"], str(guard_dir / "bash-env.sh"))
            self.assertEqual(environment["WSLENV"], "KEEP/u:BASH_ENV/p:TEMP/p:TMP/p:TMPDIR/p")
            self.assertNotIn("CLAUDECODE", environment)
            self.assertTrue(Path(call.args[0][0]).is_absolute())
            self.assertNotEqual(Path(call.args[0][0]).parent, guard_dir)
        self.assertEqual([call.args[0] for call in self.cli_resolver.call_args_list],
                         ["FAKE_CLAUDE", "FAKE_CODEX", "FAKE_CLAUDE"])

    def test_tampered_deny_shim_stops_before_any_child(self):
        (self.root / "runner-guards/bin/codex.cmd").write_text("mock altered guard")
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.assertTrue(self.pointer.exists())
        self.assertFalse(self.archive.exists())
        self.assertFalse(self.result_path.exists())
        self.popen_mock.assert_not_called()

    def test_raw_codex_uses_named_phase_and_guarded_environment(self):
        result = self.invoke()
        self.assertEqual(result["phases"][0]["name"], "codex_solve")
        command = self.popen_mock.call_args.args[0]
        self.assertEqual(command[0], self.cli_paths["FAKE_CODEX"])
        self.assertEqual(command[command.index("--sandbox") + 1], "danger-full-access")
        for feature in ("apps", "multi_agent", "multi_agent_v2", "hooks", "plugins", "remote_plugin"):
            self.assertIn(f"features.{feature}=false", command)
        self.assertIn("features.skip_host_skill_discovery=true", command)
        self.assertEqual(self.popen_mock.call_args.kwargs["env"]["PATH"].split(runner.os.pathsep)[0],
                         str(self.active_trial.parent / "runner-guards/bin"))
        self.assertEqual(result["model_calls"], 1)

    def test_suite_drift_before_trial_halts_without_starting_or_persisting(self):
        (self.input / "fixture.txt").write_text("changed original fixture")
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.assertTrue(runner.STOP.is_set())
        self.assertFalse(self.trial.exists())
        self.assertFalse(self.result_path.exists())
        self.popen_mock.assert_not_called()

    def test_suite_drift_during_model_halts_before_verifier_or_terminal_result(self):
        self.create_script = True
        self.process_hook = lambda proc: (self.input / "fixture.txt").write_text("changed during mock phase")
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.assertTrue(runner.STOP.is_set())
        self.assertFalse(self.result_path.exists())
        self.verifier.assert_not_called()
        self.assertEqual(runner.ACTIVE, {})

    def test_added_empty_suite_directory_is_critical_drift(self):
        (self.root / "suite/unplanned-directory").mkdir()
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.popen_mock.assert_not_called()
        self.assertTrue(runner.STOP.is_set())

    def test_harness_source_drift_during_model_halts_even_for_raw_arm(self):
        self.process_hook = lambda proc: (self.root / "harness-snapshot/unplanned.txt").write_text("drift")
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.assertTrue(runner.STOP.is_set())
        self.assertFalse(self.result_path.exists())

    def test_benchmark_code_drift_during_model_halts_before_verifier_or_result(self):
        expected = self.args.artifact_hashes["benchmark_code_hashes"]
        changed = {**expected, "verify_solution.py": "f" * 64}
        hashes = self.patch("benchmark_code_hashes", side_effect=[expected, changed])
        self.create_script = True
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.assertEqual(hashes.call_count, 2)
        self.assertTrue(runner.STOP.is_set())
        self.assertFalse(self.result_path.exists())
        self.assertFalse(self.archive.exists())
        self.verifier.assert_not_called()

    def test_verifier_side_effect_drift_is_critical_and_keeps_no_terminal_score(self):
        self.verifier_result()
        original_response = self.verifier.return_value

        def alter_source(*args, **kwargs):
            (self.input / "fixture.txt").write_text("source changed during grading fixture")
            return original_response
        self.verifier.side_effect = alter_source
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.assertTrue(runner.STOP.is_set())
        self.assertFalse(self.result_path.exists())

    def test_benchmark_code_drift_during_verifier_keeps_no_terminal_score(self):
        self.verifier_result()
        expected = self.args.artifact_hashes["benchmark_code_hashes"]
        changed = {**expected, "make_suite.py": "f" * 64}
        hashes = self.patch("benchmark_code_hashes", side_effect=[expected, expected, changed])
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.assertEqual(hashes.call_count, 3)
        self.verifier.assert_called_once()
        self.assertTrue(runner.STOP.is_set())
        self.assertFalse(self.result_path.exists())
        self.assertFalse(self.archive.exists())

    def test_trial_binds_sanitized_root_without_mutating_snapshot(self):
        self.use_harness()
        source = self.root / "harness-snapshot/AGENTS.md"
        source.write_text("Workspace: " + runner.TRIAL_ROOT_PLACEHOLDER)
        self.args.artifact_hashes["harness_hashes"] = runner.tree_hashes(self.root / "harness-snapshot")
        result = self.invoke()
        self.assertTrue(result["correct"])
        self.assertEqual((self.trial / "AGENTS.md").read_text(), "Workspace: " + self.active_trial.as_posix())
        self.assertIn(runner.TRIAL_ROOT_PLACEHOLDER, source.read_text())
        self.assertNotIn(runner.TRIAL_ROOT_PLACEHOLDER, (self.trial / "AGENTS.md").read_text())


class HarnessSnapshot(unittest.TestCase):
    """Copy the actual harness into a temp directory; never run its contents."""

    def test_snapshot_preserves_skill_prerequisites_without_project_permissions(self):
        critical_docs = ("PRE-CTF-INTAKE.md", "TROUBLESHOOTING.md", "SKILL-INTEGRATION.md")
        with tempfile.TemporaryDirectory(prefix="ctf-snapshot-test-") as temporary:
            destination = Path(temporary) / "snapshot"
            with mock.patch.object(runner, "run", side_effect=AssertionError("No CLI during snapshot")), \
                 mock.patch.object(runner, "wsl_python", side_effect=AssertionError("No generation during snapshot")), \
                 mock.patch.object(runner.subprocess, "Popen", side_effect=AssertionError("No child during snapshot")):
                manifest = runner.snapshot_harness(destination)
            for name in critical_docs:
                copied = destination / "docs" / name
                with self.subTest(document=name):
                    self.assertTrue(copied.is_file())
                    self.assertGreater(copied.stat().st_size, 0)
                    self.assertEqual(manifest["docs/" + name], hashlib.sha256(copied.read_bytes()).hexdigest())

            integration = (destination / "docs/SKILL-INTEGRATION.md").resolve()
            for tree_name in (".claude/skills", ".agents/skills"):
                tree = destination / tree_name
                self.assertTrue(tree.is_dir(), tree_name)
                skills = {path.parent.name: path for path in tree.glob("*/SKILL.md")}
                source_names = {path.parent.name for path in (ROOT / tree_name).glob("*/SKILL.md")}
                self.assertTrue(source_names, "Source skills must be present for a meaningful snapshot test")
                self.assertEqual(set(skills), source_names)
                for name, skill in skills.items():
                    with self.subTest(tree=tree_name, skill=name):
                        links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", skill.read_text(encoding="utf-8"))
                        prerequisite_links = [link.strip("<>") for link in links if "docs/SKILL-INTEGRATION.md" in link]
                        self.assertTrue(prerequisite_links, f"Missing integration prerequisite in {skill}")
                        for link in prerequisite_links:
                            parsed = urlsplit(link)
                            self.assertFalse(parsed.scheme or parsed.netloc, "Prerequisite must be snapshot-local")
                            target = (skill.parent / unquote(parsed.path)).resolve()
                            self.assertTrue(target.is_relative_to(destination.resolve()), "Prerequisite escapes snapshot")
                            self.assertEqual(target, integration)
                            self.assertTrue(target.is_file(), "Copied skill has a dangling prerequisite")

            # The benchmark supplies matched tool permissions through CLI flags.
            self.assertTrue((ROOT / ".claude/settings.json").is_file())
            self.assertFalse((destination / ".claude/settings.json").exists())
            self.assertNotIn(".claude/settings.json", manifest)
            wrapper = destination / "tools/codex-crosscheck.sh"
            self.assertEqual(wrapper.read_bytes(), runner.CROSSCHECK_DISABLED.encode("utf-8"))
            self.assertIn("exit 126", wrapper.read_text())
            self.assertNotIn("exec ", wrapper.read_text())
            self.assertEqual(manifest["tools/codex-crosscheck.sh"],
                             runner.guard_hashes()["harness/tools/codex-crosscheck.sh"])
            self.assertNotEqual(wrapper.read_bytes(), (ROOT / "tools/codex-crosscheck.sh").read_bytes())
            for excluded in ("README.md", "setup.ps1", "docs/BOOTSTRAP.md", "tools/check-workspace.py",
                             "tools/workspace-manifest.json", "tools/wsl", "benchmarks"):
                self.assertFalse((destination / excluded).exists(), excluded)
            self.assertTrue((destination / "tools/vendor-ctf-skills/LICENSE").is_file())
            roots = (str(ROOT).lower(), ROOT.as_posix().lower(), runner.wsl_path(ROOT).lower())
            for path in destination.rglob("*"):
                if path.is_file():
                    text = path.read_text(encoding="utf-8").lower()
                    self.assertFalse(any(root in text for root in roots), str(path))
                    self.assertNotRegex(text, r"benchmarks[/\\]", str(path))
            self.assertIn(runner.TRIAL_ROOT_PLACEHOLDER, (destination / "AGENTS.md").read_text(encoding="utf-8"))


class TreeDigest(unittest.TestCase):
    def test_new_master_seed_is_32_random_bytes_and_cannot_overwrite_private_state(self):
        with tempfile.TemporaryDirectory(prefix="ctf-private-seed-unit-") as temporary:
            root = Path(temporary)
            with mock.patch.object(runner.secrets, "token_bytes", wraps=runner.secrets.token_bytes) as entropy:
                commitment = runner.create_private_seed(root)
            entropy.assert_called_once_with(32)
            seed = runner.read_private_seed(root)
            self.assertEqual(len(seed), 32)
            self.assertEqual(commitment, hashlib.sha256(seed).hexdigest())
            with self.assertRaises(FileExistsError):
                runner.create_private_seed(root)
            self.assertTrue(runner.read_private_seed(root) == seed)

    def test_digest_is_stable_for_manifest_order_and_detects_content_or_tree_changes(self):
        manifest = {"input/": "directory hash", "input/fixture.txt": "inert file hash"}
        before = runner.tree_digest(manifest)
        self.assertRegex(before, r"^[0-9a-f]{64}$")
        self.assertEqual(before, runner.tree_digest(dict(reversed(list(manifest.items())))))
        self.assertNotEqual(before, runner.tree_digest({**manifest, "input/fixture.txt": "changed hash"}))
        self.assertNotEqual(before, runner.tree_digest({**manifest, "new-empty/": "directory hash"}))
        self.assertNotEqual(before, runner.tree_digest({"input/": "directory hash"}))

    def test_result_and_protocol_hmacs_use_exact_separate_domain_labels(self):
        with tempfile.TemporaryDirectory(prefix="ctf-hmac-unit-") as temporary:
            root = Path(temporary)
            runner.create_private_seed(root)
            seed = runner.read_private_seed(root)
            result = {"z": "한글", "a": [2, 1], "result_hmac_sha256": "ignored"}
            protocol = {"z": "한글", "a": [2, 1], "protocol_hmac_sha256": "ignored"}
            canonical = json.dumps({"a": [2, 1], "z": "한글"}, sort_keys=True,
                                   separators=(",", ":"), ensure_ascii=True,
                                   allow_nan=False).encode("utf-8")
            result_key = hmac.new(seed, b"ctf-benchmark/protocol-v6/result-hmac-key\0",
                                  hashlib.sha256).digest()
            protocol_key = hmac.new(seed, b"ctf-benchmark/protocol-v6/protocol-hmac-key\0",
                                    hashlib.sha256).digest()
            expected_result = hmac.new(result_key, canonical, hashlib.sha256).hexdigest()
            expected_protocol = hmac.new(protocol_key, canonical, hashlib.sha256).hexdigest()
            self.assertEqual(runner.result_hmac_sha256(root, result), expected_result)
            self.assertEqual(runner.protocol_hmac_sha256(root, protocol), expected_protocol)
            self.assertNotEqual(expected_result, expected_protocol)


class WslPythonCommand(unittest.TestCase):
    def test_direct_interpreter_preserves_script_and_each_argument_without_shell(self):
        script = ROOT / "benchmarks/inert argv fixture.py"
        translated = "/mnt/e/inert fixtures/한글 argv.py"
        arguments = ("/mnt/c/input folder", "alpha", "beta", "literal $HOME;$(ignored)", "", 2)
        response = SimpleNamespace(returncode=0, stdout="inert metadata", stderr="")
        with mock.patch.object(runner, "wsl_path", return_value=translated) as path, \
             mock.patch.object(runner.subprocess, "run", return_value=response) as command, \
             mock.patch.object(runner.subprocess, "Popen", side_effect=AssertionError("No actual WSL process")):
            result = runner.wsl_python(script, *arguments, timeout=17)
        path.assert_called_once_with(script)
        command.assert_called_once_with(
            ["wsl", "-d", "ubuntu-ctf", "--", "/home/ctf/.ctf-tools/venv/bin/python",
             "-I", translated, "/mnt/c/input folder", "alpha", "beta", "literal $HOME;$(ignored)", "", "2"],
            text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=17)
        self.assertIs(result, response)


class GuardConfiguration(unittest.TestCase):
    def test_deny_sources_and_exact_byte_hashes_cover_bash_cmd_and_powershell(self):
        with tempfile.TemporaryDirectory(prefix="ctf-guards-mock-") as temporary:
            root = Path(temporary)
            runner.install_guards(root)
            directory = runner.verify_guards(root)
            expected_names = {name + suffix for name in ("claude", "codex")
                              for suffix in ("", ".cmd", ".bat", ".ps1")} | {"bash-env.sh"}
            self.assertEqual({p.name for p in directory.iterdir()}, expected_names)
            for name in expected_names:
                content = (directory / name).read_bytes()
                self.assertEqual(hashlib.sha256(content).hexdigest(), runner.guard_hashes()[name])
                if name != "bash-env.sh":
                    self.assertIn(b"disabled", content)
                    self.assertIn(b"126", content)
            self.assertIn(b"BASH_SOURCE", (directory / "bash-env.sh").read_bytes())
            self.assertIn(b"export PATH=", (directory / "bash-env.sh").read_bytes())
            with self.assertRaises(FileExistsError):
                runner.install_guards(root)

    def test_parent_cli_is_resolved_before_command_uses_child_guard_path(self):
        with tempfile.TemporaryDirectory(prefix="ctf-cli-resolution-mock-") as temporary:
            root = Path(temporary)
            actual = root / "native tools/claude.exe"
            args = SimpleNamespace(claude="claude", codex="codex", claude_model="fixture", codex_model="fixture")
            with mock.patch.object(runner.shutil, "which", return_value=str(actual)) as which, \
                 mock.patch.object(runner.subprocess, "Popen", side_effect=AssertionError("No native CLI")):
                command = runner.phase_command(root, "claude_raw", "claude_solve", "claude", args)
            which.assert_called_once_with("claude")
            self.assertEqual(command[0], str(actual.resolve()))
            self.assertIn("--safe-mode", command)


class ResumeProtocol(unittest.TestCase):
    """Resume validation exercises main(), with all process/generator calls blocked."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ctf-resume-mock-")
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.repo = base / "repo"
        (self.repo / "benchmarks").mkdir(parents=True)
        (self.repo / "benchmarks/runner_fixture.py").write_text("# inert source-hash fixture\n")
        self.root = base / "results"
        self.root.mkdir()
        runner.STOP.clear()
        self.addCleanup(runner.STOP.clear)
        runner.install_guards(self.root)
        stub = self.root / "harness-snapshot/tools/codex-crosscheck.sh"
        stub.parent.mkdir(parents=True)
        stub.write_bytes(runner.CROSSCHECK_DISABLED.encode("utf-8"))
        (self.root / "suite").mkdir()
        (self.root / "suite/fixture.txt").write_text("inert manifest fixture, no generated task")
        self.protocol = {
            "protocol_version": runner.PROTOCOL_VERSION, "suite_version": runner.SUITE_VERSION,
            "arms": list(runner.ARMS), **private_fixture(self.root, "layered-r1"),
            "phase_plans": runner.phase_protocol(),
            "workspace_isolation": dict(runner.WORKSPACE_ISOLATION),
            "provider_execution": json.loads(json.dumps(runner.PROVIDER_EXECUTION)),
            "nested_cli_guard_hashes": runner.guard_hashes(),
            "suite_hashes": runner.tree_hashes(self.root / "suite"),
            "harness_hashes": runner.tree_hashes(self.root / "harness-snapshot"), "intake": {},
            "repeats": 1, "tasks": ["layered"], "timeout": 240, "workers": 2,
            "claude_model": "fake-model", "codex_model": "fake-model", "specs": runner.build_specs(["layered"], 1),
            "benchmark_code_hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in (self.repo / "benchmarks").glob("*.py")},
            "cli_versions": {"claude": "fake-claude 1", "codex": "fake-codex 1"},
        }
        self.protocol["protocol_hmac_sha256"] = runner.protocol_hmac_sha256(self.root, self.protocol)
        self.unseen_baseline = unseen_fixture("layered-r1")
        self.argv = ["run_benchmark.py", "--root", str(self.root), "--intake", str(base / "unused.json"),
                     "--repeats", "1", "--tasks", "layered", "--timeout", "240", "--workers", "2",
                     "--claude", "FAKE_CLAUDE", "--codex", "FAKE_CODEX",
                     "--claude-model", "fake-model", "--codex-model", "fake-model", "--prepare-only"]

    def invoke(self, *, resign=True):
        if resign:
            self.protocol["protocol_hmac_sha256"] = runner.protocol_hmac_sha256(self.root, self.protocol)
        path = self.root / "protocol.json"
        path.write_text(json.dumps(self.protocol))
        before = path.read_bytes()

        def version_only(command, **kwargs):
            self.assertEqual(command[1:], ["--version"])
            return SimpleNamespace(stdout={"FAKE_CLAUDE": "fake-claude 1", "FAKE_CODEX": "fake-codex 1"}[command[0]],
                                   stderr="", returncode=0)

        # Replace the runner's os binding, not os.name globally (Path must stay native).
        with mock.patch.object(runner, "os", SimpleNamespace(**{**vars(runner.os), "name": "nt"})), \
             mock.patch.object(runner, "REPO", self.repo), \
             mock.patch.object(runner, "check_intake", return_value={}), \
             mock.patch.object(runner, "run", side_effect=version_only), \
             mock.patch.object(runner, "wsl_python", return_value=SimpleNamespace(returncode=0, stderr="",
                               stdout=json.dumps(self.unseen_baseline))), \
             mock.patch.object(runner.subprocess, "Popen", side_effect=AssertionError("Native CLI forbidden")), \
             mock.patch.object(runner.sys, "argv", self.argv), \
             redirect_stdout(io.StringIO()), mock.patch("sys.stderr", new_callable=io.StringIO):
            try:
                return runner.main()
            finally:
                self.assertEqual(path.read_bytes(), before, "Resume validation must preserve the existing protocol")

    def test_compatible_resume_prepare_only_checks_commitments_without_model(self):
        self.assertIsNone(self.invoke())

    def test_unsigned_protocol_rewrites_are_rejected_before_fields_are_trusted(self):
        baseline = json.loads(json.dumps(self.protocol))
        changes = {
            "plan": lambda value: value["phase_plans"]["project_harness"].pop(),
            "tasks": lambda value: value["tasks"].clear(),
            "repeats": lambda value: value.__setitem__("repeats", 2),
            "specs": lambda value: value["specs"].pop(),
            "commitments": lambda value: value["unseen_commitments"].pop("layered-r1"),
            "suite_hashes": lambda value: value["suite_hashes"].clear(),
        }
        for field, change in changes.items():
            with self.subTest(field=field):
                runner.STOP.clear()
                self.protocol = json.loads(json.dumps(baseline))
                change(self.protocol)
                with self.assertRaises(runner.CriticalIntegrityError):
                    self.invoke(resign=False)
                self.assertTrue(runner.STOP.is_set())

    def test_protocol_symlink_shape_is_rejected(self):
        path = self.root / "protocol.json"
        path.write_text(json.dumps(self.protocol))
        original_lstat = Path.lstat

        def report_protocol_as_symlink(candidate):
            if candidate == path:
                return SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)
            return original_lstat(candidate)

        with mock.patch.object(Path, "lstat", new=report_protocol_as_symlink):
            with self.assertRaises(runner.CriticalIntegrityError):
                runner.load_valid_protocol(self.root, path)
        self.assertTrue(runner.STOP.is_set())

    def test_changed_timeout_rejects_resume(self):
        self.protocol["timeout"] = 120
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)

    def test_old_two_by_two_protocol_cannot_resume(self):
        self.protocol.pop("protocol_version")
        self.protocol["specs"] = [{"provider": "claude", "condition": "baseline"}]
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)

    def test_protocol_v4_cannot_resume_under_changed_provider_execution(self):
        self.protocol["protocol_version"] = 4
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)

    def test_protocol_v5_and_previous_suites_cannot_resume(self):
        self.protocol["protocol_version"] = 5
        with self.assertRaises(SystemExit):
            self.invoke()
        self.protocol["protocol_version"] = 6
        for version in (1, 2):
            with self.subTest(suite_version=version):
                self.protocol["suite_version"] = version
                with self.assertRaises(SystemExit):
                    self.invoke()

    def test_private_seed_tamper_rejects_resume(self):
        (self.root / runner.MASTER_SEED_PATH).write_bytes(b"x" * 32)
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()

    def test_changed_unseen_commitment_digest_rejects_resume(self):
        self.protocol["unseen_commitments_sha256"] = "f" * 64
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()

    def test_regeneration_rejects_coherently_modified_unseen_commitments(self):
        self.protocol["unseen_commitments"]["layered-r1"]["flag_sha256"] = "f" * 64
        self.protocol["unseen_commitments_sha256"] = runner.tree_digest(self.protocol["unseen_commitments"])
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()

    def test_missing_provider_execution_policy_rejects_resume(self):
        self.protocol.pop("provider_execution")
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)

    def test_provider_execution_permission_guard_or_trace_drift_rejects_resume(self):
        changes = (("claude", "permission_mode", "changed"), ("claude", "tools", ["Read"]),
                   ("codex", "sandbox", "read-only"), ("codex", "approval_policy", "on-request"),
                   ("nested_model_calls", "guard", "none"), ("nested_model_calls", "trace", "none"),
                   ("codex_review", "enforcement", "prompt-only"))
        for section, field, replacement in changes:
            with self.subTest(section=section, field=field):
                self.protocol["provider_execution"] = json.loads(json.dumps(runner.PROVIDER_EXECUTION))
                self.protocol["provider_execution"][section][field] = replacement
                with self.assertRaises(SystemExit) as error:
                    self.invoke()
                self.assertEqual(error.exception.code, 2)

    def test_missing_or_duplicate_arm_rejects_resume(self):
        self.protocol["specs"][0] = dict(self.protocol["specs"][1])
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)

    def test_changed_phase_cap_rejects_resume(self):
        self.protocol["phase_plans"]["project_harness"][0]["cap_seconds"] = 240
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)

    def test_changed_guard_hash_protocol_rejects_resume(self):
        self.protocol["nested_cli_guard_hashes"]["claude"] = "changed"
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)

    def test_changed_intake_confirmation_rejects_resume(self):
        self.protocol["intake"] = {"user_confirmation": "different confirmation"}
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)

    def test_changed_suite_after_prepare_is_critical_on_resume(self):
        (self.root / "suite/fixture.txt").write_text("changed after preparation")
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.assertTrue(runner.STOP.is_set())

    def test_changed_harness_after_prepare_is_critical_on_resume(self):
        (self.root / "harness-snapshot/new-file.md").write_text("unplanned")
        with self.assertRaises(runner.CriticalIntegrityError):
            self.invoke()
        self.assertTrue(runner.STOP.is_set())

    def test_changed_guard_file_rejects_resume_without_repair(self):
        path = self.root / "runner-guards/bin/codex.ps1"
        path.write_bytes(b"mock changed guard")
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(path.read_bytes(), b"mock changed guard")

    def test_changed_snapshot_stub_rejects_resume_without_repair(self):
        path = self.root / "harness-snapshot/tools/codex-crosscheck.sh"
        path.write_bytes(b"mock changed stub")
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(path.read_bytes(), b"mock changed stub")

    def test_default_plan_is_36_trials_with_three_arms_per_input(self):
        specs = runner.build_specs(runner.DEFAULT_TASKS, 2)
        self.assertEqual(len(specs), 36)
        self.assertEqual(len({s["id"] for s in specs}), 36)
        inputs = {s["instance"] for s in specs}
        self.assertEqual(len(inputs), 12)
        for instance in inputs:
            arms = [s["arm"] for s in specs if s["instance"] == instance]
            self.assertCountEqual(arms, ["claude_raw", "codex_raw", "project_harness"])
        self.assertEqual(specs, runner.build_specs(runner.DEFAULT_TASKS, 2), "Scheduling is reproducible")

    def test_changed_workers_rejects_resume(self):
        self.protocol["workers"] = 1
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)

    def test_changed_workspace_isolation_or_schedule_rejects_resume(self):
        self.protocol["workspace_isolation"]["schedule_seed"] += 1
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)

    def test_instance_blocks_keep_every_complete_prefix_arm_balanced(self):
        specs = runner.build_specs(runner.DEFAULT_TASKS, 2)
        blocks = [specs[index:index + 3] for index in range(0, len(specs), 3)]
        for index, block in enumerate(blocks):
            self.assertEqual(len({s["instance"] for s in block}), 1)
            self.assertEqual([s["arm"] for s in block],
                             list(runner.ARMS[index % 3:] + runner.ARMS[:index % 3]))
            counts = Counter(spec["arm"] for spec in specs[:(index + 1) * 3])
            self.assertEqual(counts, {arm: index + 1 for arm in runner.ARMS})
        for start in range(0, len(blocks), 3):
            for position in range(3):
                self.assertCountEqual([block[position]["arm"] for block in blocks[start:start + 3]], runner.ARMS)

    def test_global_preflight_rejects_later_pointer_before_any_execution(self):
        later = self.protocol["specs"][-1]
        runner.save(runner.pointer_path(self.root, later), {"state": "uninspected", "pid": 424242})
        with mock.patch.object(runner.subprocess, "Popen", side_effect=AssertionError("No CLI")) as child:
            with self.assertRaises(runner.RecoveryRequiredError):
                runner.assert_no_partial_trials(self.root, self.protocol["specs"])
            child.assert_not_called()

    def test_global_preflight_rejects_incoming_and_archive_without_result(self):
        archives = self.root / "trials"
        archives.mkdir()
        incoming = archives / ".incoming-mock-crash"
        incoming.mkdir()
        with self.assertRaises(runner.RecoveryRequiredError):
            runner.assert_no_partial_trials(self.root, self.protocol["specs"])
        incoming.rmdir()
        later = self.protocol["specs"][-1]
        (archives / later["id"]).mkdir()
        with self.assertRaises(runner.RecoveryRequiredError):
            runner.assert_no_partial_trials(self.root, self.protocol["specs"])
        runner.save(self.root / "results" / (later["id"] + ".json"), {"status": "completed"})
        runner.assert_no_partial_trials(self.root, self.protocol["specs"])

    def test_new_protocol_persists_requested_workers_without_generating_tasks(self):
        fresh_root = self.root.parent / "fresh-run"
        argv = self.argv.copy()
        argv[argv.index("--root") + 1] = str(fresh_root)
        argv[argv.index("--workers") + 1] = "1"

        def metadata_only(command, **kwargs):
            if command == ["git", "rev-parse", "HEAD"]:
                return SimpleNamespace(stdout="fake-head", stderr="", returncode=0)
            self.assertEqual(command[1:], ["--version"])
            return SimpleNamespace(stdout={"FAKE_CLAUDE": "fake-claude 1", "FAKE_CODEX": "fake-codex 1"}[command[0]],
                                   stderr="", returncode=0)

        def snapshot_fixture(destination):
            stub = destination / "tools/codex-crosscheck.sh"
            stub.parent.mkdir(parents=True)
            stub.write_bytes(runner.CROSSCHECK_DISABLED.encode("utf-8"))
            return runner.tree_hashes(destination)

        def generator_metadata_only(*args, **kwargs):
            # Directory fixture only: no tasks, answers, binaries or models.
            if Path(args[0]).name == "make_suite.py":
                self.assertIn("main", args)
                self.assertIn("--master-seed-file", args)
                (fresh_root / "suite").mkdir()
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            self.assertEqual(Path(args[0]).name, "verify_solution.py")
            self.assertIn("--commitments", args)
            self.assertIn("--master-seed-file", args)
            return SimpleNamespace(returncode=0, stdout=json.dumps(self.unseen_baseline), stderr="")

        # main() writes only protocol metadata: the snapshot and generator are mocks.
        with mock.patch.object(runner, "os", SimpleNamespace(**{**vars(runner.os), "name": "nt"})), \
             mock.patch.object(runner, "REPO", self.repo), \
             mock.patch.object(runner, "check_intake", return_value={}), \
             mock.patch.object(runner, "run", side_effect=metadata_only), \
             mock.patch.object(runner, "snapshot_harness", side_effect=snapshot_fixture), \
             mock.patch.object(runner, "wsl_path", return_value="/mock/path"), \
             mock.patch.object(runner, "wsl_python", side_effect=generator_metadata_only) as generator, \
             mock.patch.object(runner.subprocess, "Popen", side_effect=AssertionError("Native CLI forbidden")), \
             mock.patch.object(runner.sys, "argv", argv), redirect_stdout(io.StringIO()):
            runner.main()
        saved = json.loads((fresh_root / "protocol.json").read_text())
        self.assertEqual(saved.get("workers"), 1, "Worker concurrency is part of the experimental protocol")
        self.assertEqual(saved["arms"], list(runner.ARMS))
        self.assertEqual(saved["phase_plans"], runner.phase_protocol())
        self.assertEqual(saved["workspace_isolation"], runner.WORKSPACE_ISOLATION)
        self.assertEqual(saved["provider_execution"], runner.PROVIDER_EXECUTION)
        self.assertEqual(saved["nested_cli_guard_hashes"], runner.guard_hashes())
        self.assertEqual(saved["suite_hashes"], {})
        self.assertEqual(saved["harness_hashes"], runner.tree_hashes(fresh_root / "harness-snapshot"))
        self.assertEqual((fresh_root / "runner-guards/bin/codex.cmd").read_bytes(), runner.DENY_CMD.encode("utf-8"))
        self.assertEqual(len(saved["specs"]), 3)
        self.assertEqual(generator.call_count, 2)
        self.assertEqual(saved["suite_version"], runner.SUITE_VERSION)
        self.assertEqual(saved["protocol_version"], 6)
        self.assertEqual(saved["protocol_hmac_sha256"],
                         runner.protocol_hmac_sha256(fresh_root, saved))
        self.assertEqual(saved["unseen_commitments"], self.unseen_baseline)
        self.assertEqual(saved["unseen_commitments_sha256"], runner.tree_digest(self.unseen_baseline))
        seed = (fresh_root / runner.MASTER_SEED_PATH).read_bytes()
        self.assertEqual(len(seed), 32)
        self.assertEqual(saved["master_seed_sha256"], hashlib.sha256(seed).hexdigest())
        self.assertFalse(seed.hex() in json.dumps(saved))
        self.assertFalse(CANDIDATE in json.dumps(saved))
        self.assertFalse((fresh_root / "unseen").exists())
        self.assertFalse((fresh_root / "harness-snapshot/.private").exists())
        self.assertEqual(list((fresh_root / "suite").iterdir()), [], "Mock generator must not create challenge data")

    def test_changed_benchmark_source_rejects_resume(self):
        self.protocol["benchmark_code_hashes"] = {"runner_fixture.py": "changed"}
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)

    def test_changed_cli_version_rejects_resume(self):
        self.protocol["cli_versions"]["codex"] = "fake-codex 0"
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
