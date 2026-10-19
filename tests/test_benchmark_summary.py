"""Reject misleading aggregations using dummy outcomes, without model calls."""
import copy
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("summary", Path(__file__).resolve().parents[1] / "benchmarks/summarize.py")
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


class SummaryTests(unittest.TestCase):
    CLAUDE_MODEL = "claude-test-model"
    CODEX_MODEL = "codex-test-model"
    MASTER_SEED = hashlib.sha256(b"inert summary fixture master seed").digest()
    MAIN_FLAG = "BENCH{" + "1" * 32 + "}"
    MAIN_FLAG_SHA256 = hashlib.sha256(MAIN_FLAG.encode()).hexdigest()

    @staticmethod
    def original_bytes(instance):
        return f"inert original input for {instance}\n".encode()

    def spec(self, arm, instance="dummy-r1", *, task="dummy", repeat=1):
        metadata = summary.ARM_METADATA[arm]
        return {"id": f"{arm}-{instance}", "arm": arm, **metadata,
                "task": task, "instance": instance, "repeat": repeat}

    def commitment(self, instance):
        hashes = {"fixture.bin": summary.canonical_sha256({"unseen-input": instance})}
        return {"hashes": hashes, "input_digest": summary.canonical_sha256(hashes),
                "flag_sha256": summary.canonical_sha256({"unseen-flag": instance})}

    def protocol(self, *, task="dummy", repeats=1, specs=None, **overrides):
        if specs is None:
            specs = [self.spec(arm, f"{task}-r{repeat}", task=task, repeat=repeat)
                     for repeat in range(1, repeats + 1) for arm in summary.ARMS]
        instances = {item["instance"] for item in specs if isinstance(item, dict)
                     and isinstance(item.get("instance"), str)}
        commitments = {instance: self.commitment(instance) for instance in instances}
        answer_key = {instance: {"flag_sha256": self.MAIN_FLAG_SHA256}
                      for instance in sorted(instances)}
        answer_bytes = (json.dumps(answer_key, ensure_ascii=False, indent=2) + "\n").encode()
        directory_digest = hashlib.sha256(b"directory").hexdigest()
        suite_hashes = {"answer-key.json": hashlib.sha256(answer_bytes).hexdigest()}
        for instance in sorted(instances):
            suite_hashes.update({
                f"{instance}/": directory_digest,
                f"{instance}/untrusted/": directory_digest,
                f"{instance}/untrusted/input.bin": hashlib.sha256(
                    self.original_bytes(instance)).hexdigest(),
            })
        value = {"protocol_version": summary.PROTOCOL_VERSION,
                 "suite_version": summary.SUITE_VERSION,
                 "master_seed_sha256": hashlib.sha256(self.MASTER_SEED).hexdigest(),
                 "unseen_commitments": commitments,
                 "unseen_commitments_sha256": summary.canonical_sha256(commitments),
                 "suite_hashes": suite_hashes,
                 "benchmark_code_hashes": summary.benchmark_code_hashes(),
                 "arms": list(summary.ARMS),
                 "phase_plans": summary.phase_protocol(), "timeout": summary.TOTAL_BUDGET_SECONDS,
                 "provider_execution": json.loads(json.dumps(summary.PROVIDER_EXECUTION)),
                 "workers": 1, "tasks": [task], "repeats": repeats,
                 "claude_model": self.CLAUDE_MODEL, "codex_model": self.CODEX_MODEL,
                 "specs": specs}
        value.update(overrides)
        value[summary.PROTOCOL_HMAC_FIELD] = summary.compute_protocol_hmac(
            value, summary.derive_protocol_hmac_key(self.MASTER_SEED))
        return value

    def phase(self, name, provider, cap, *, budget=None, status="completed", usage=None,
              tool_calls=1, elapsed=1.0, process_started=True):
        budget = cap if budget is None else budget
        requested_model = self.CLAUDE_MODEL if provider == "claude" else self.CODEX_MODEL
        return {"name": name, "provider": provider, "requested_model": requested_model,
                "observed_model": requested_model, "read_only": name == "codex_review",
                "usage": usage or {},
                "tool_calls": tool_calls, "exit_code": 0 if status == "completed" else 1,
                "status": status, "timeout": status == "timeout",
                "process_started": process_started, "cap_seconds": cap,
                "budget_seconds": budget, "elapsed_seconds": elapsed}

    def row(self, trial_spec, *, correct=True, phases=None, status="completed", timeout=False,
            same_instance=None, new_instance=None, verification_status=None):
        if phases is None:
            phases = [self.phase(*plan) for plan in summary.PHASE_PLANS[trial_spec["arm"]]]
        commitment = self.commitment(trial_spec["instance"])
        verification_status = verification_status or ("ran" if status == "completed" else "not_run")
        ran = verification_status == "ran"
        same_instance = correct if same_instance is None and ran else bool(same_instance)
        new_instance = correct if new_instance is None and ran else bool(new_instance)
        same_execution = self.execution(self.MAIN_FLAG_SHA256 if same_instance else None) if ran else summary.empty_safe_execution()
        new_execution = self.execution(commitment["flag_sha256"] if new_instance else None) if ran else summary.empty_safe_execution()
        verification = {
            "status": verification_status, "same_instance": same_instance,
            "new_instance": new_instance,
            "same_execution": same_execution, "new_execution": new_execution,
            "unseen_hashes": commitment["hashes"] if ran else {},
            "unseen_input_digest": commitment["input_digest"] if ran else None,
            "new_expected_flag_sha256": commitment["flag_sha256"] if ran else None,
            "expected_unseen_hashes": commitment["hashes"],
            "expected_unseen_input_digest": commitment["input_digest"],
            "expected_unseen_flag_sha256": commitment["flag_sha256"],
            "unseen_hashes_match": ran, "unseen_digest_match": ran, "unseen_flag_hash_match": ran,
            "unseen_commitment_match": ran,
            "verifier_process": self.verifier_process() if ran else summary.empty_verifier_process(),
            "error_type": None,
        }
        return {**trial_spec, "correct": correct, "timeout": timeout, "status": status,
                "turn_completed": status == "completed",
                "final": self.MAIN_FLAG if correct else "unsolved",
                "elapsed_seconds": sum(p["elapsed_seconds"] for p in phases),
                "tool_calls": sum(p["tool_calls"] for p in phases),
                "model_calls": sum(p["process_started"] for p in phases),
                "writeup_present": True, "originals_unchanged": True,
                "unseen_commitment": commitment,
                "verification": verification,
                "phases": phases}

    @staticmethod
    def execution(candidate_hash=None):
        output = b"candidate-output" if candidate_hash else b""
        candidates = [candidate_hash] if candidate_hash else []
        return {"returncode": 0, "stdout_bytes": len(output),
                "stdout_sha256": hashlib.sha256(output).hexdigest(),
                "stderr_bytes": 0, "stderr_sha256": summary.EMPTY_SHA256,
                "candidate_flag_count": len(candidates),
                "candidate_flag_sha256s": candidates}

    @staticmethod
    def verifier_process():
        output = b'{"safe":"verification"}\n'
        return {"returncode": 0, "stdout_bytes": len(output),
                "stdout_sha256": hashlib.sha256(output).hexdigest(),
                "stderr_bytes": 0, "stderr_sha256": summary.EMPTY_SHA256}

    def write_result(self, root, row):
        private = root / ".private"
        private.mkdir(exist_ok=True)
        (private / "master-seed.bin").write_bytes(self.MASTER_SEED)
        suite = root / "suite"
        suite.mkdir(exist_ok=True)
        answer_path = suite / "answer-key.json"
        answer_key = json.loads(answer_path.read_text()) if answer_path.exists() else {}
        answer_key[row["instance"]] = {"flag_sha256": self.MAIN_FLAG_SHA256}
        answer_path.write_bytes((json.dumps(answer_key, ensure_ascii=False, indent=2) + "\n").encode())
        prepared_untrusted = suite / row["instance"] / "untrusted"
        prepared_untrusted.mkdir(parents=True, exist_ok=True)
        (prepared_untrusted / "input.bin").write_bytes(self.original_bytes(row["instance"]))
        archive = root / "trials" / row["id"]
        archive.mkdir(parents=True, exist_ok=True)
        archived_untrusted = (archive / "events" / "local-benchmark" / "challenges"
                              / row["instance"] / "untrusted")
        archived_untrusted.mkdir(parents=True, exist_ok=True)
        (archived_untrusted / "input.bin").write_bytes(self.original_bytes(row["instance"]))
        marker = archive / "terminal-evidence.txt"
        if not marker.exists():
            marker.write_text("inert archived trial evidence\n", encoding="utf-8")
        row["archive_path"] = f"trials/{row['id']}"
        row["archive_tree_digest"] = summary.canonical_sha256(summary.tree_hashes(archive))
        row[summary.RESULT_HMAC_FIELD] = summary.compute_result_hmac(
            row, summary.derive_result_hmac_key(self.MASTER_SEED))
        (root / "results").mkdir(exist_ok=True)
        (root / "results" / f"{row['id']}.json").write_text(json.dumps(row), encoding="utf-8")

    def resign_result(self, root, row):
        row[summary.RESULT_HMAC_FIELD] = summary.compute_result_hmac(
            row, summary.derive_result_hmac_key(self.MASTER_SEED))
        (root / "results" / f"{row['id']}.json").write_text(json.dumps(row), encoding="utf-8")

    def write_protocol(self, root, protocol):
        private = root / ".private"
        private.mkdir(exist_ok=True)
        (private / "master-seed.bin").write_bytes(self.MASTER_SEED)
        (root / "protocol.json").write_text(json.dumps(protocol), encoding="utf-8")

    def replace_with_symlink(self, path):
        target = path.with_name(path.name + "-target")
        path.rename(target)
        try:
            path.symlink_to(target, target_is_directory=target.is_dir())
        except OSError as error:
            target.rename(path)
            self.skipTest(f"symlinks unavailable: {error}")
        return target

    def load_results(self, root, protocol):
        return summary.load_results(
            root, protocol, commitment_regenerator=lambda _root, value: value["unseen_commitments"])

    def aggregate(self, root):
        return summary.aggregate(
            root, commitment_regenerator=lambda _root, value: value["unseen_commitments"])

    def review(self, **overrides):
        scores = {"hypothesis": 2, "commands": 2, "observations": 1, "writeup": 2}
        value = {
            "reviewer": "reviewer-A",
            "reviewer_scores": scores,
            "adjudicator": "reviewer-B",
            "adjudicator_scores": {**scores, "observations": 2},
            "scores": {**scores, "observations": 2},
            "evidence": {name: f"logs/trial/{name}:1" for name in scores},
            "adjudication": "Observation score changed after checking the raw log.",
            "compliance": {name: "pass" for name in summary.COMPLIANCE},
        }
        value.update(overrides)
        return value

    def test_claude_cache_is_part_of_prompt_total(self):
        result = summary.usage_totals("claude", [{"usage": {"input_tokens": 10, "cache_read_input_tokens": 30,
            "cache_creation_input_tokens": 20, "output_tokens": 4}}, {"usage": {}}])
        self.assertEqual(result["prompt_tokens"], 60)
        self.assertEqual(result["reported_trials"], 1)
        self.assertEqual(result["missing_trials"], 1)

    def test_codex_cached_tokens_are_not_counted_twice(self):
        result = summary.usage_totals("codex", [{"usage": {"input_tokens": 100, "cached_input_tokens": 60, "output_tokens": 5}}])
        self.assertEqual(result["prompt_tokens"], 100)
        self.assertEqual(result["cache_read_tokens"], 60)

    def test_missing_usage_is_not_zero(self):
        self.assertIsNone(summary.usage_totals("codex", [{"usage": {}}])["prompt_tokens"])

    def test_protocol_v6_envelope_is_strict(self):
        cases = []
        missing_version = self.protocol()
        missing_version.pop("protocol_version")
        cases.append((missing_version, "version"))
        changed_suite = self.protocol(suite_version=1)
        cases.append((changed_suite, "Suite version"))
        previous_suite = self.protocol(suite_version=2)
        cases.append((previous_suite, "Suite version"))
        bad_master = self.protocol(master_seed_sha256="A" * 64)
        cases.append((bad_master, "master_seed_sha256"))
        changed_arms = self.protocol(arms=list(reversed(summary.ARMS)))
        cases.append((changed_arms, "arms"))
        changed_plan = self.protocol()
        changed_plan["phase_plans"]["project_harness"][1]["read_only"] = False
        cases.append((changed_plan, "phase plans"))
        changed_timeout = self.protocol(timeout=120)
        cases.append((changed_timeout, "timeout"))
        missing_model = self.protocol(codex_model="")
        cases.append((missing_model, "models"))
        for protocol, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    summary.validate_protocol(protocol)

    def test_protocol_v5_and_provider_policy_drift_are_rejected(self):
        version_five = self.protocol(protocol_version=5)
        with self.assertRaisesRegex(ValueError, "version must be 6"):
            summary.validate_protocol(version_five)

        mutations = [
            ("claude permission", ("claude", "permission_mode"), "default"),
            ("codex sandbox", ("codex", "sandbox"), "read-only"),
            ("trace limitation", ("nested_model_calls", "limitation"), "none"),
            ("review enforcement", ("codex_review", "enforcement"), "prompt-only"),
        ]
        for label, (section, field), replacement in mutations:
            with self.subTest(label=label):
                protocol = self.protocol()
                protocol["provider_execution"][section][field] = replacement
                with self.assertRaisesRegex(ValueError, "provider execution policy"):
                    summary.validate_protocol(protocol)

    def test_missing_or_tampered_unseen_commitments_are_rejected(self):
        missing = self.protocol()
        missing["unseen_commitments"].pop("dummy-r1")
        missing["unseen_commitments_sha256"] = summary.canonical_sha256(
            missing["unseen_commitments"])
        with self.assertRaisesRegex(ValueError, "cover every instance"):
            summary.validate_protocol(missing)

        tampered = self.protocol()
        tampered["unseen_commitments"]["dummy-r1"]["hashes"]["fixture.bin"] = "0" * 64
        tampered["unseen_commitments_sha256"] = summary.canonical_sha256(
            tampered["unseen_commitments"])
        with self.assertRaisesRegex(ValueError, "Tampered unseen commitment"):
            summary.validate_protocol(tampered)

        bad_aggregate = self.protocol(unseen_commitments_sha256="f" * 64)
        with self.assertRaisesRegex(ValueError, "digest does not match"):
            summary.validate_protocol(bad_aggregate)

        for field in ["input_digest", "flag_sha256"]:
            with self.subTest(field=field):
                invalid_hash = self.protocol()
                invalid_hash["unseen_commitments"]["dummy-r1"][field] = "A" * 64
                invalid_hash["unseen_commitments_sha256"] = summary.canonical_sha256(
                    invalid_hash["unseen_commitments"])
                with self.assertRaisesRegex(ValueError, "Tampered unseen commitment"):
                    summary.validate_protocol(invalid_hash)

        invalid_path = self.protocol()
        entry = invalid_path["unseen_commitments"]["dummy-r1"]
        digest = entry["hashes"].pop("fixture.bin")
        entry["hashes"]["../fixture.bin"] = digest
        entry["input_digest"] = summary.canonical_sha256(entry["hashes"])
        invalid_path["unseen_commitments_sha256"] = summary.canonical_sha256(
            invalid_path["unseen_commitments"])
        with self.assertRaisesRegex(ValueError, "Invalid unseen input hashes"):
            summary.validate_protocol(invalid_path)

    def test_protocol_requires_complete_consistent_three_arm_cells(self):
        incomplete = self.protocol()
        incomplete["specs"].pop()
        with self.assertRaisesRegex(ValueError, "three-arm"):
            summary.validate_protocol(incomplete)
        inconsistent = self.protocol()
        inconsistent["specs"][1]["task"] = "other"
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            summary.validate_protocol(inconsistent)

    def test_unplanned_result_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            row = self.row(self.spec("claude_raw"))
            row["id"] = "extra"
            self.write_result(root, row)
            with self.assertRaisesRegex(ValueError, "planned"):
                self.load_results(root, self.protocol())

    def test_duplicate_protocol_ids_rejected(self):
        entry = self.spec("claude_raw")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            summary.validate_protocol(self.protocol(specs=[entry, entry]))

    def test_timeout_success_rejected(self):
        entry = self.spec("codex_raw")
        row = self.row(entry, phases=[self.phase("codex_solve", "codex", 240, status="timeout")],
                       correct=True, status="timeout", timeout=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            self.write_result(root, row)
            with self.assertRaisesRegex(ValueError, "timed out"):
                self.load_results(root, self.protocol())

    def test_changed_condition_rejected(self):
        entry = self.spec("codex_raw")
        row = {**self.row(entry), "condition": "harness"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            self.write_result(root, row)
            with self.assertRaisesRegex(ValueError, "metadata mismatch"):
                self.load_results(root, self.protocol())

    def test_result_unseen_commitment_mismatch_is_rejected(self):
        entry = self.spec("claude_raw")
        for target in ["top", "verification"]:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "results").mkdir()
                row = self.row(entry)
                if target == "top":
                    row["unseen_commitment"]["input_digest"] = "0" * 64
                else:
                    row["verification"]["unseen_input_digest"] = "0" * 64
                    row["verification"]["unseen_digest_match"] = False
                    row["verification"]["unseen_commitment_match"] = False
                self.write_result(root, row)
                with self.assertRaisesRegex(ValueError, "commitment"):
                    self.load_results(root, self.protocol())

    def test_unknown_verification_status_is_rejected(self):
        entry = self.spec("claude_raw")
        row = self.row(entry)
        row["verification"]["status"] = "maybe"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            self.write_result(root, row)
            with self.assertRaisesRegex(ValueError, "verification outcome"):
                self.load_results(root, self.protocol())

    def test_completed_trial_requires_the_full_phase_plan(self):
        entry = self.spec("project_harness")
        row = self.row(entry, phases=[self.phase("claude_solve", "claude", 120)],
                       correct=False, status="completed")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            self.write_result(root, row)
            with self.assertRaisesRegex(ValueError, "marked completed"):
                self.load_results(root, self.protocol())

    def test_trial_timeout_flag_and_status_must_agree(self):
        entry = self.spec("claude_raw")
        row = self.row(entry, correct=False, status="timeout", timeout=False)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            self.write_result(root, row)
            with self.assertRaisesRegex(ValueError, "Inconsistent trial timeout"):
                self.load_results(root, self.protocol())

    def test_protocol_arm_metadata_mismatch_rejected(self):
        protocol = self.protocol()
        protocol["specs"][1]["provider"] = "claude"
        with self.assertRaisesRegex(ValueError, "metadata mismatch"):
            summary.validate_protocol(protocol)

    def test_phase_sequence_and_budget_are_enforced(self):
        entry = self.spec("project_harness")
        row = self.row(entry, phases=[self.phase("codex_review", "codex", 60)], correct=False)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            self.write_result(root, row)
            with self.assertRaisesRegex(ValueError, "Phase protocol mismatch"):
                self.load_results(root, self.protocol())

    def test_phase_requested_model_and_access_mode_are_enforced(self):
        entry = self.spec("project_harness")
        for field, value in [("requested_model", "wrong-model"), ("read_only", False)]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "results").mkdir()
                phases = [self.phase(*plan) for plan in summary.PHASE_PLANS[entry["arm"]]]
                phases[1][field] = value
                self.write_result(root, self.row(entry, phases=phases, correct=False))
                with self.assertRaisesRegex(ValueError, "model or access"):
                    self.load_results(root, self.protocol())

    def test_phase_budget_may_shrink_but_not_exceed_cap(self):
        entry = self.spec("project_harness")
        valid = [self.phase("claude_solve", "claude", 120, budget=110)]
        invalid = [self.phase("claude_solve", "claude", 120, budget=121)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            self.write_result(root, self.row(entry, phases=valid, correct=False,
                                             status="infrastructure_error"))
            self.assertEqual(len(self.load_results(root, self.protocol())), 1)
            self.write_result(root, self.row(entry, phases=invalid, correct=False,
                                             status="infrastructure_error"))
            with self.assertRaisesRegex(ValueError, "Invalid phase budget"):
                self.load_results(root, self.protocol())

    def test_zero_remaining_budget_is_a_valid_timeout_only(self):
        entry = self.spec("project_harness")
        first = self.phase("claude_solve", "claude", 120)
        zero_timeout = self.phase("codex_review", "codex", 60, budget=0,
                                  status="timeout", tool_calls=0, elapsed=0, process_started=False)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            valid = self.row(entry, phases=[first, zero_timeout], correct=False,
                             status="timeout", timeout=True)
            self.write_result(root, valid)
            self.assertEqual(len(self.load_results(root, self.protocol())), 1)
            invalid = self.row(entry, phases=[first, self.phase(
                "codex_review", "codex", 60, budget=0, tool_calls=0, elapsed=0,
                process_started=False)], correct=False)
            self.write_result(root, invalid)
            with self.assertRaisesRegex(ValueError, "Invalid phase budget"):
                self.load_results(root, self.protocol())

    def test_total_deadline_timeout_need_not_be_a_phase_timeout(self):
        entry = self.spec("project_harness")
        phases = [self.phase(*plan) for plan in summary.PHASE_PLANS[entry["arm"]]]
        row = self.row(entry, phases=phases, correct=False, status="timeout", timeout=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            self.write_result(root, row)
            self.assertTrue(self.load_results(root, self.protocol())[0]["timeout"])

    def test_model_call_count_must_equal_started_processes(self):
        entry = self.spec("claude_raw")
        row = {**self.row(entry), "model_calls": 0}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            self.write_result(root, row)
            with self.assertRaisesRegex(ValueError, "model-call count"):
                self.load_results(root, self.protocol())

    def test_correct_harness_requires_every_completed_phase(self):
        entry = self.spec("project_harness")
        row = self.row(entry, phases=[self.phase(*summary.PHASE_PLANS[entry["arm"]][0])], correct=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            self.write_result(root, row)
            with self.assertRaisesRegex(ValueError, "completed required phase"):
                self.load_results(root, self.protocol())

    def test_prelaunch_infrastructure_failure_may_have_no_phases(self):
        entry = self.spec("claude_raw")
        row = self.row(entry, correct=False, phases=[], status="infrastructure_error")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            self.write_result(root, row)
            self.assertEqual(self.load_results(root, self.protocol())[0]["status"],
                             "infrastructure_error")

    def test_slow_infrastructure_failure_duration_is_preserved(self):
        entry = self.spec("claude_raw")
        phase = self.phase("claude_solve", "claude", 240, status="infrastructure_error",
                           elapsed=600.0)
        row = self.row(entry, phases=[phase], correct=False, status="infrastructure_error")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            self.write_result(root, row)
            loaded = self.load_results(root, self.protocol())
            self.assertEqual(loaded[0]["phases"][0]["elapsed_seconds"], 600.0)

    def test_result_hmac_rejects_new_instance_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.protocol()
            row = self.row(protocol["specs"][0], new_instance=False)
            self.write_result(root, row)
            stored = json.loads((root / "results" / f"{row['id']}.json").read_text())
            stored["verification"]["new_instance"] = True
            (root / "results" / f"{row['id']}.json").write_text(json.dumps(stored))
            with self.assertRaisesRegex(ValueError, "HMAC mismatch"):
                self.load_results(root, protocol)

    def test_protocol_hmac_rejects_tampering_before_plan_is_trusted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.protocol()
            self.write_protocol(root, protocol)
            protocol["workers"] = 2
            with self.assertRaisesRegex(ValueError, "Protocol HMAC mismatch"):
                summary.load_results(root, protocol,
                    commitment_regenerator=lambda _root, value: value["unseen_commitments"])

    def test_protocol_file_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_protocol(root, self.protocol())
            self.replace_with_symlink(root / "protocol.json")
            with self.assertRaisesRegex(ValueError, "regular non-linked file"):
                self.aggregate(root)

    def test_coherent_plan_shrink_is_rejected_by_protocol_hmac(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.protocol(repeats=2)
            for trial_spec in protocol["specs"]:
                self.write_result(root, self.row(trial_spec))
            self.write_protocol(root, protocol)
            removed = [spec for spec in protocol["specs"] if spec["repeat"] == 2]
            for trial_spec in removed:
                (root / "results" / f"{trial_spec['id']}.json").unlink()
            answer_key = {"dummy-r1": {"flag_sha256": self.MAIN_FLAG_SHA256}}
            (root / "suite/answer-key.json").write_bytes(
                (json.dumps(answer_key, ensure_ascii=False, indent=2) + "\n").encode())
            (root / "suite/dummy-r2/untrusted/input.bin").unlink()
            (root / "suite/dummy-r2/untrusted").rmdir()
            (root / "suite/dummy-r2").rmdir()
            protocol["repeats"] = 1
            protocol["specs"] = [spec for spec in protocol["specs"] if spec["repeat"] == 1]
            protocol["unseen_commitments"].pop("dummy-r2")
            protocol["unseen_commitments_sha256"] = summary.canonical_sha256(
                protocol["unseen_commitments"])
            protocol["suite_hashes"] = summary.tree_hashes(root / "suite")
            (root / "protocol.json").write_text(json.dumps(protocol), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Protocol HMAC mismatch"):
                self.aggregate(root)

    def test_benchmark_code_hash_map_rejects_added_deleted_and_changed_sources(self):
        baseline = summary.benchmark_code_hashes()
        first = next(iter(baseline))
        mutations = {
            "added": {**baseline, "unexpected.py": "0" * 64},
            "deleted": {name: digest for name, digest in baseline.items() if name != first},
            "changed": {**baseline, first: "0" * 64},
        }
        for label, hashes in mutations.items():
            with self.subTest(label=label):
                protocol = self.protocol(benchmark_code_hashes=hashes)
                with self.assertRaisesRegex(ValueError, "Benchmark source files"):
                    summary.validate_benchmark_code_hashes(protocol)

    def test_benchmark_code_mismatch_fails_before_unseen_regeneration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.protocol()
            first = next(iter(protocol["benchmark_code_hashes"]))
            protocol["benchmark_code_hashes"][first] = "0" * 64
            protocol[summary.PROTOCOL_HMAC_FIELD] = summary.compute_protocol_hmac(
                protocol, summary.derive_protocol_hmac_key(self.MASTER_SEED))
            self.write_protocol(root, protocol)
            called = []
            with self.assertRaisesRegex(ValueError, "Benchmark source files"):
                summary.load_results(root, protocol,
                    commitment_regenerator=lambda *_args: called.append(True))
            self.assertEqual(called, [])

    def test_signed_verification_boolean_must_match_observed_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.protocol()
            row = self.row(protocol["specs"][0], new_instance=False)
            self.write_result(root, row)
            row["verification"]["new_instance"] = True
            self.resign_result(root, row)
            with self.assertRaisesRegex(ValueError, "safe evidence"):
                self.load_results(root, protocol)

    def test_repeated_same_flag_is_valid_evidence_but_not_a_reproduction_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.protocol()
            row = self.row(protocol["specs"][0])
            row["verification"]["same_execution"]["candidate_flag_count"] = 2
            row["verification"]["same_instance"] = False
            self.write_result(root, row)
            loaded = self.load_results(root, protocol)[0]
            self.assertFalse(loaded["verification"]["same_instance"])
            self.assertFalse(summary.reproducible_success(loaded))

    def test_safe_evidence_rejects_false_empty_stream_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.protocol()
            row = self.row(protocol["specs"][0])
            row["verification"]["same_execution"]["stderr_sha256"] = "0" * 64
            self.write_result(root, row)
            with self.assertRaisesRegex(ValueError, "Empty execution stream"):
                self.load_results(root, protocol)

    def test_runner_safe_verifier_failure_shapes_are_accepted_without_success(self):
        for shape in ["nonzero_process", "commitment_mismatch", "caught_error"]:
            with self.subTest(shape=shape), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                protocol = self.protocol()
                row = self.row(protocol["specs"][0])
                verification = row["verification"]
                if shape == "nonzero_process":
                    verification["verifier_process"]["returncode"] = 1
                    verification["same_instance"] = False
                    verification["new_instance"] = False
                elif shape == "commitment_mismatch":
                    hashes = {"fixture.bin": "0" * 64}
                    verification.update({
                        "status": "verification_infrastructure_error",
                        "same_instance": False,
                        "new_instance": False,
                        "unseen_hashes": hashes,
                        "unseen_input_digest": summary.canonical_sha256(hashes),
                        "unseen_hashes_match": False,
                        "unseen_digest_match": False,
                        "unseen_flag_hash_match": True,
                        "unseen_commitment_match": False,
                        "error": next(iter(summary.ALLOWED_VERIFICATION_ERRORS)),
                    })
                else:
                    row = self.row(protocol["specs"][0], verification_status="missing_script")
                    verification = row["verification"]
                    verification["status"] = "verification_infrastructure_error"
                    verification["error_type"] = "JSONDecodeError"
                    verification["verifier_process"] = self.verifier_process()
                self.write_result(root, row)
                loaded = self.load_results(root, protocol)[0]
                self.assertFalse(summary.reproducible_success(loaded))

    def test_verification_error_cannot_store_arbitrary_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.protocol()
            row = self.row(protocol["specs"][0], verification_status="missing_script")
            row["verification"].update({
                "status": "verification_infrastructure_error",
                "error": "raw verifier stderr must not be stored",
            })
            self.write_result(root, row)
            with self.assertRaisesRegex(ValueError, "error evidence"):
                self.load_results(root, protocol)

    def test_missing_result_hmac_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.protocol()
            row = self.row(protocol["specs"][0])
            self.write_result(root, row)
            row.pop(summary.RESULT_HMAC_FIELD)
            (root / "results" / f"{row['id']}.json").write_text(json.dumps(row))
            with self.assertRaisesRegex(ValueError, "HMAC mismatch"):
                self.load_results(root, protocol)

    def test_result_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.protocol()
            row = self.row(protocol["specs"][0])
            self.write_result(root, row)
            self.replace_with_symlink(root / "results" / f"{row['id']}.json")
            with self.assertRaisesRegex(ValueError, "regular non-linked file"):
                self.load_results(root, protocol)

    def test_archive_path_and_tree_mutations_are_rejected(self):
        for mutation, message in [("path", "archive path"), ("content", "archive tree")]:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                protocol = self.protocol()
                row = self.row(protocol["specs"][0])
                self.write_result(root, row)
                if mutation == "path":
                    row["archive_path"] = "trials/another-id"
                    self.resign_result(root, row)
                else:
                    (root / row["archive_path"] / "added-after-seal.txt").write_text("tampered")
                with self.assertRaisesRegex(ValueError, message):
                    self.load_results(root, protocol)

    def test_missing_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.protocol()
            row = self.row(protocol["specs"][0])
            self.write_result(root, row)
            archive = root / row["archive_path"]
            archive.rename(archive.with_name(archive.name + "-missing"))
            with self.assertRaisesRegex(ValueError, "Missing artifact tree"):
                self.load_results(root, protocol)

    def test_archive_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.protocol()
            row = self.row(protocol["specs"][0])
            self.write_result(root, row)
            self.replace_with_symlink(root / row["archive_path"])
            with self.assertRaisesRegex(ValueError, "regular non-linked directory"):
                self.load_results(root, protocol)

    def test_trials_parent_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.protocol()
            row = self.row(protocol["specs"][0])
            self.write_result(root, row)
            self.replace_with_symlink(root / "trials")
            with self.assertRaisesRegex(ValueError, "trials directory must be a regular non-linked directory"):
                self.load_results(root, protocol)

    def test_originals_unchanged_is_recomputed_from_archive(self):
        for mutation in ["false_claim", "changed_archive"]:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                protocol = self.protocol()
                row = self.row(protocol["specs"][0])
                self.write_result(root, row)
                archive = root / row["archive_path"]
                if mutation == "false_claim":
                    row["originals_unchanged"] = False
                else:
                    archived_input = (archive / "events" / "local-benchmark" / "challenges"
                                      / row["instance"] / "untrusted" / "input.bin")
                    archived_input.write_bytes(b"changed after the trial\n")
                    row["archive_tree_digest"] = summary.canonical_sha256(summary.tree_hashes(archive))
                self.resign_result(root, row)
                with self.assertRaisesRegex(ValueError, "Originals integrity result"):
                    self.load_results(root, protocol)

    def test_honest_changed_originals_remain_a_protocol_violation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.protocol()
            row = self.row(protocol["specs"][0])
            self.write_result(root, row)
            archive = root / row["archive_path"]
            archived_input = (archive / "events" / "local-benchmark" / "challenges"
                              / row["instance"] / "untrusted" / "input.bin")
            archived_input.write_bytes(b"changed during the trial\n")
            row["originals_unchanged"] = False
            row["archive_tree_digest"] = summary.canonical_sha256(summary.tree_hashes(archive))
            self.resign_result(root, row)
            loaded = self.load_results(root, protocol)
            self.assertEqual(summary.protocol_status(loaded[0], {}), "violation")

    def test_honest_missing_archived_originals_remain_a_protocol_violation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.protocol()
            row = self.row(protocol["specs"][0])
            self.write_result(root, row)
            archive = root / row["archive_path"]
            archived_untrusted = (archive / "events" / "local-benchmark" / "challenges"
                                  / row["instance"] / "untrusted")
            archived_untrusted.rename(archived_untrusted.with_name("untrusted-missing"))
            row["originals_unchanged"] = False
            row["archive_tree_digest"] = summary.canonical_sha256(summary.tree_hashes(archive))
            self.resign_result(root, row)
            loaded = self.load_results(root, protocol)
            self.assertEqual(summary.protocol_status(loaded[0], {}), "violation")

    def test_coherent_commitment_rewrite_is_rejected_by_regeneration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.protocol()
            baseline = copy.deepcopy(protocol["unseen_commitments"])
            row = self.row(protocol["specs"][0])
            self.write_result(root, row)
            commitment = protocol["unseen_commitments"][row["instance"]]
            commitment["hashes"] = {"fixture.bin": "0" * 64}
            commitment["input_digest"] = summary.canonical_sha256(commitment["hashes"])
            commitment["flag_sha256"] = "f" * 64
            protocol["unseen_commitments_sha256"] = summary.canonical_sha256(
                protocol["unseen_commitments"])
            protocol[summary.PROTOCOL_HMAC_FIELD] = summary.compute_protocol_hmac(
                protocol, summary.derive_protocol_hmac_key(self.MASTER_SEED))
            with self.assertRaisesRegex(ValueError, "Regenerated unseen commitments"):
                summary.load_results(root, protocol,
                    commitment_regenerator=lambda _root, _protocol: baseline)

    def test_raw_verifier_output_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.protocol()
            row = self.row(protocol["specs"][0])
            row["verification"]["same_stdout"] = self.MAIN_FLAG
            self.write_result(root, row)
            with self.assertRaisesRegex(ValueError, "verification outcome"):
                self.load_results(root, protocol)

    def test_signed_status_tampering_is_rejected_by_terminal_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.protocol()
            row = self.row(protocol["specs"][0], correct=False)
            self.write_result(root, row)
            row["status"] = "infrastructure_error"
            self.resign_result(root, row)
            with self.assertRaisesRegex(ValueError, "completion evidence"):
                self.load_results(root, protocol)

    def test_planned_commitment_pairs_are_distinct_from_observed_digest_pairs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reviews").mkdir()
            protocol = self.protocol()
            specs = {item["arm"]: item for item in protocol["specs"]}
            (root / "protocol.json").write_text(json.dumps(protocol))
            rows = [self.row(specs["claude_raw"], verification_status="missing_script"),
                    self.row(specs["codex_raw"]), self.row(specs["project_harness"])]
            for row in rows:
                self.write_result(root, row)
            comparisons = {item["raw_arm"]: item for item in self.aggregate(root)["comparisons"]}
            claude = comparisons["claude_raw"]
            self.assertEqual(claude["pairs_with_matching_planned_unseen_commitment"], 1)
            self.assertEqual(claude["pairs_with_matching_observed_unseen_digest"], 0)
            self.assertEqual(comparisons["codex_raw"]["pairs_with_matching_observed_unseen_digest"], 1)
            group = self.aggregate(root)["groups"][0]
            self.assertNotIn("protocol_valid_correct", group)
            self.assertIn("primary_success_count", group)

    def test_review_requires_distinct_raters_and_both_raw_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reviews").mkdir()
            review = self.review(adjudicator="reviewer-A")
            (root / "reviews/evidence.json").write_text(json.dumps({"a": review}))
            with self.assertRaisesRegex(ValueError, "independent"):
                summary.load_reviews(root, [{"id": "a"}])
            review = self.review()
            review.pop("reviewer_scores")
            (root / "reviews/evidence.json").write_text(json.dumps({"a": review}))
            with self.assertRaisesRegex(ValueError, "reviewer"):
                summary.load_reviews(root, [{"id": "a"}])

    def test_primary_metric_is_null_until_all_reviews_are_resolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            (root / "reviews").mkdir()
            protocol = self.protocol()
            (root / "protocol.json").write_text(json.dumps(protocol))
            rows = [self.row(spec) for spec in protocol["specs"]]
            for row in rows:
                self.write_result(root, row)

            interim = self.aggregate(root)
            self.assertFalse(interim["primary_metric_ready"])
            self.assertTrue(all(group["primary_success_rate_all_attempts"] is None
                                for group in interim["groups"]))
            self.assertTrue(all(item["primary_success_delta_pp_all_pairs"] is None
                                for item in interim["comparisons"]))

            reviews = {row["id"]: self.review() for row in rows}
            reviews[rows[0]["id"]] = self.review(compliance={
                **{name: "pass" for name in summary.COMPLIANCE}, "external_access": "unknown"})
            (root / "reviews/evidence.json").write_text(json.dumps(reviews))
            unresolved = self.aggregate(root)
            self.assertFalse(unresolved["primary_metric_ready"])
            self.assertIsNone(unresolved["groups"][0]["primary_success_rate_protocol_valid_only"])

            reviews[rows[0]["id"]] = self.review()
            (root / "reviews/evidence.json").write_text(json.dumps(reviews))
            final = self.aggregate(root)
            self.assertTrue(final["primary_metric_ready"])
            self.assertTrue(all(group["primary_success_rate_all_attempts"] == 1.0
                                for group in final["groups"]))
            self.assertTrue(all(item["primary_success_delta_pp_all_pairs"] == 0.0
                                for item in final["comparisons"]))

    def test_same_and_unseen_reproduction_are_required_for_primary_success(self):
        for failed_field in ["same_instance", "new_instance"]:
            with self.subTest(failed_field=failed_field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "results").mkdir()
                (root / "reviews").mkdir()
                protocol = self.protocol()
                specs = {item["arm"]: item for item in protocol["specs"]}
                (root / "protocol.json").write_text(json.dumps(protocol))
                rows = [self.row(specs[arm]) for arm in summary.ARMS]
                rows[0]["verification"][failed_field] = False
                execution_field = "same_execution" if failed_field == "same_instance" else "new_execution"
                rows[0]["verification"][execution_field] = self.execution()
                for row in rows:
                    self.write_result(root, row)
                (root / "reviews/evidence.json").write_text(json.dumps(
                    {row["id"]: self.review() for row in rows}))

                aggregate = self.aggregate(root)
                group = next(item for item in aggregate["groups"]
                             if item["arm"] == "claude_raw")
                self.assertEqual(group["mechanical_flag_correct"], 1)
                self.assertEqual(group["rate_mechanical_flag_correct_all_attempts"], 1.0)
                self.assertEqual(group["reproducible_correct"], 0)
                self.assertEqual(group["rate_reproducible_correct_all_attempts"], 0.0)
                self.assertEqual(group["primary_success_count"], 0)
                self.assertEqual(group["primary_success_rate_all_attempts"], 0.0)
                self.assertIsNone(group["primary_success_median_seconds"])
                comparison = next(item for item in aggregate["comparisons"]
                                  if item["raw_arm"] == "claude_raw")
                self.assertEqual(comparison["mechanical_both"], 1)
                self.assertEqual(comparison["reproducible_harness_only"], 1)
                self.assertEqual(comparison["primary_success_harness_only"], 1)
                self.assertEqual(comparison["primary_success_delta_pp_all_pairs"], 100.0)

    def test_aggregate_reports_rater_agreement_and_valid_sensitivity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            (root / "reviews").mkdir()
            protocol = self.protocol()
            specs = {item["arm"]: item for item in protocol["specs"]}
            (root / "protocol.json").write_text(json.dumps(protocol))
            phases = [
                self.phase("claude_solve", "claude", 120,
                           usage={"input_tokens": 10, "output_tokens": 2}),
                self.phase("codex_review", "codex", 60,
                           usage={"input_tokens": 20, "cached_input_tokens": 5, "output_tokens": 3}),
                self.phase("claude_finalize", "claude", 60,
                           budget=50,
                           usage={"input_tokens": 30, "cache_read_input_tokens": 4, "output_tokens": 5}),
            ]
            rows = [self.row(specs["claude_raw"]), self.row(specs["codex_raw"]),
                    self.row(specs["project_harness"], phases=phases)]
            for row in rows:
                self.write_result(root, row)
            (root / "reviews/evidence.json").write_text(json.dumps(
                {row["id"]: self.review() for row in rows}))
            aggregate = self.aggregate(root)
            group = next(item for item in aggregate["groups"] if item["arm"] == "project_harness")
            self.assertTrue(aggregate["primary_metric_ready"])
            self.assertEqual(group["evidence_rater_exact_agreements"], 3)
            self.assertEqual(group["evidence_rater_comparisons"], 4)
            self.assertEqual(group["evidence_rater_exact_agreement_rate"], 0.75)
            self.assertEqual(group["primary_success_rate_protocol_valid_only"], 1.0)
            self.assertEqual(group["primary_success_rate_all_attempts"], 1.0)
            self.assertEqual(group["model_calls_observed"], 3)
            self.assertEqual(group["token_totals_by_provider"]["claude"]["prompt_tokens"], 44)
            self.assertEqual(group["token_totals_by_provider"]["codex"]["prompt_tokens"], 20)

    def test_pair_comparisons_use_the_same_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            protocol = self.protocol()
            specs = protocol["specs"]
            (root / "protocol.json").write_text(json.dumps(protocol))
            rows = [self.row(specs[0], correct=False), self.row(specs[1], correct=True),
                    self.row(specs[2], correct=True)]
            for row in rows:
                self.write_result(root, row)
            comparisons = {item["raw_arm"]: item for item in self.aggregate(root)["comparisons"]}
            self.assertEqual(comparisons["claude_raw"]["mechanical_harness_only"], 1)
            self.assertEqual(comparisons["claude_raw"]["mechanical_success_delta_pp_all_pairs"], 100)
            self.assertEqual(comparisons["codex_raw"]["mechanical_both"], 1)
            self.assertEqual(comparisons["codex_raw"]["reproducible_both"], 1)
            self.assertEqual(comparisons["claude_raw"]["pairs_with_matching_planned_unseen_commitment"], 1)
            self.assertEqual(comparisons["claude_raw"]["pairs_with_matching_observed_unseen_digest"], 1)
            self.assertEqual(comparisons["claude_raw"]["primary_success_harness_only"], 0)
            self.assertIsNone(comparisons["claude_raw"]["primary_success_delta_pp_all_pairs"])

    def test_correct_but_noncompliant_trial_is_not_protocol_valid_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            (root / "reviews").mkdir()
            protocol = self.protocol()
            specs = {item["arm"]: item for item in protocol["specs"]}
            (root / "protocol.json").write_text(json.dumps(protocol))
            rows = [self.row(specs[arm], correct=True) for arm in summary.ARMS]
            for row in rows:
                self.write_result(root, row)
            review = self.review(compliance={**{name: "pass" for name in summary.COMPLIANCE},
                                             "cross_trial_access": "violation"})
            reviews = {row["id"]: self.review() for row in rows}
            reviews[specs["claude_raw"]["id"]] = review
            (root / "reviews/evidence.json").write_text(json.dumps(reviews))
            aggregate = self.aggregate(root)
            group = next(item for item in aggregate["groups"] if item["arm"] == "claude_raw")
            self.assertTrue(aggregate["primary_metric_ready"])
            self.assertEqual(group["mechanical_flag_correct"], 1)
            self.assertEqual(group["rate_mechanical_flag_correct_all_attempts"], 1.0)
            self.assertEqual(group["reproducible_correct"], 1)
            self.assertEqual(group["primary_success_rate_all_attempts"], 0.0)
            self.assertEqual(group["protocol_status_counts"]["violation"], 1)


if __name__ == "__main__":
    unittest.main()
