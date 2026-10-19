"""Focused invariants for the deterministic benchmark suite v3 generator."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("benchmark_suite_v3", ROOT / "benchmarks" / "make_suite.py")
suite = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(suite)

SEED_A = bytes(range(32))
SEED_B = bytes(reversed(range(32)))


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix())
        if path.is_file()
    }


class SuiteV3Tests(unittest.TestCase):
    def test_seed_is_required_and_exactly_256_bits(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(TypeError):
                suite.generate(Path(temporary) / "missing", 1)
            with self.assertRaises(ValueError):
                suite.generate(Path(temporary) / "short", 1, b"short")
            with self.assertRaises(ValueError):
                suite.generate(Path(temporary) / "bad-hex", 1, "00" * 31)

    def test_same_seed_and_domain_are_byte_identical_and_domains_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            suite.generate(base / "first", 1, SEED_A, "main")
            suite.generate(base / "second", 1, SEED_A.hex(), "main")
            suite.generate(base / "unseen", 1, SEED_A, "unseen")
            suite.generate(base / "other-seed", 1, SEED_B, "main")
            suite.generate(base / "hard-forward", 1, SEED_A, "main", tasks=sorted(suite.HARD_TASKS))
            suite.generate(base / "hard-reverse", 1, SEED_A, "main", tasks=sorted(suite.HARD_TASKS, reverse=True))
            first = snapshot(base / "first")
            self.assertEqual(first, snapshot(base / "second"))
            self.assertNotEqual(first, snapshot(base / "unseen"))
            self.assertNotEqual(first, snapshot(base / "other-seed"))
            self.assertEqual(snapshot(base / "hard-forward"), snapshot(base / "hard-reverse"))

    def test_hard_instance_faults_and_uniqueness(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "suite"
            suite.generate(root, 1, SEED_A, tasks=sorted(suite.HARD_TASKS))

            lcg_folder = root / "lcg_stream-r1" / "untrusted"
            lcg_doc = json.loads((lcg_folder / "stream.json").read_text(encoding="utf-8"))
            _, lcg = suite.reference_decode_instance("lcg_stream", lcg_folder)
            self.assertNotIn("modulus", lcg_doc)
            self.assertEqual(len(lcg_doc["observations"]), 18)
            self.assertEqual(lcg["candidate_count"], 1)
            self.assertEqual(lcg["matching_observations"], 16)
            self.assertEqual(len(lcg["fault_positions"]), 2)
            self.assertEqual(lcg["modulus"].bit_length(), 31)
            self.assertTrue(suite._is_probable_prime(lcg["modulus"]))
            self.assertGreater(lcg["modulus"], max(lcg_doc["observations"]))

            rsa_folder = root / "shared_rsa-r1" / "untrusted"
            rsa_doc = json.loads((rsa_folder / "public.json").read_text(encoding="utf-8"))
            _, rsa = suite.reference_decode_instance("shared_rsa", rsa_folder)
            self.assertEqual(rsa_doc["e"], 3)
            self.assertEqual(len(rsa_doc["samples"]), 4)
            self.assertIsInstance(rsa_doc["modulus"], int)
            self.assertTrue(all("modulus" not in row for row in rsa_doc["samples"]))
            offsets = [row["offset"] for row in rsa_doc["samples"]]
            self.assertEqual(len(set(offsets)), 4)
            self.assertTrue(all(offset > 0 for offset in offsets))
            self.assertEqual(rsa["candidate_count"], 1)
            self.assertEqual(len(set(rsa["matching_indexes"])), 3)
            self.assertNotIn(rsa["corrupt_index"], rsa["matching_indexes"])

            vm_folder = root / "byte_machine-r1" / "untrusted"
            vm_doc = json.loads((vm_folder / "program.json").read_text(encoding="utf-8"))
            _, vm = suite.reference_decode_instance("byte_machine", vm_folder)
            expected_ops = {
                "xor_key", "add_const", "xor_state", "add_index", "rotate_left", "multiply_odd"
            }
            self.assertEqual(set(vm["opcode_order"]), expected_ops)
            self.assertEqual(len(vm["opcode_order"]), len(expected_ops))
            self.assertEqual(vm_doc["format"], "stateful-byte-vm-v3")
            self.assertNotIn("expected", vm_doc)
            observed = bytes.fromhex(vm_doc["observed_low6"])
            self.assertEqual(len(observed), 39)
            self.assertTrue(all(value <= 0x3F for value in observed))
            self.assertEqual(vm["solution_count"], 1)
            self.assertLessEqual(vm["max_frontier_states"], 256)
            self.assertGreaterEqual(len(vm["locally_ambiguous_positions"]), 4)
            self.assertEqual(vm["final_state"], vm_doc["final_state"])
            self.assertIn("state_update", vm_doc)
            self.assertFalse((vm_folder / "checker.py").exists())
            self.assertFalse(any(vm_folder.glob("*.py")))

            fragment_folder = root / "fragment_log-r1" / "untrusted"
            rows = [json.loads(line) for line in (fragment_folder / "capture.jsonl").read_text().splitlines()]
            metadata = next(row for row in rows if row.get("event") == "start")
            target = metadata["transfer"]
            data_rows = [row for row in rows if row.get("event") == "data" and row.get("transfer") == target]
            invalid = [
                row for row in data_rows
                if (zlib.crc32(base64.b64decode(row["data"])) & 0xFFFFFFFF) != row["crc32"]
            ]
            _, fragment = suite.reference_decode_instance("fragment_log", fragment_folder)
            self.assertIn(metadata["chunk_size"], range(7, 12))
            self.assertEqual(metadata["parity"], ["xor", "gf256"])
            self.assertEqual(metadata["gf256_polynomial"], 0x11B)
            self.assertEqual(len(metadata["coefficients"]), metadata["chunks"])
            self.assertEqual(len(set(metadata["coefficients"])), metadata["chunks"])
            self.assertTrue(all(1 <= value <= 255 for value in metadata["coefficients"]))
            self.assertEqual(len(metadata["payload_sha256"]), 64)
            self.assertEqual(len(invalid), 1)
            self.assertEqual(fragment["bad_crc_count"], 1)
            self.assertEqual(len(fragment["missing_sequences"]), 2)
            self.assertEqual(fragment["parity_kinds"], ["gf256", "xor"])
            sequence_counts = {
                seq: sum(row["seq"] == seq for row in data_rows)
                for seq in range(metadata["chunks"])
            }
            self.assertTrue(all(sequence_counts[seq] == 0 for seq in fragment["missing_sequences"]))
            self.assertEqual(sequence_counts[fragment["bad_sequence"]], 2)
            self.assertEqual(sum(count == 2 for count in sequence_counts.values()), 1)

    def test_old_shortcuts_are_invalidated_and_forward_models_roundtrip(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "suite"
            suite.generate(root, 1, SEED_A, tasks=sorted(suite.HARD_TASKS))

            lcg_folder = root / "lcg_stream-r1" / "untrusted"
            lcg_doc = json.loads((lcg_folder / "stream.json").read_text())
            self.assertNotIn("modulus", lcg_doc)
            lcg_candidates = suite._lcg_candidates(lcg_doc)
            self.assertEqual(len(lcg_candidates), 1)
            candidate = lcg_candidates[0]
            states = candidate["states"]
            self.assertTrue(all(
                states[index + 1]
                == (candidate["a"] * states[index] + candidate["c"]) % candidate["modulus"]
                for index in range(len(states) - 1)
            ))

            rsa_folder = root / "shared_rsa-r1" / "untrusted"
            rsa_doc = json.loads((rsa_folder / "public.json").read_text())
            rsa_plaintext, rsa = suite.reference_decode_instance("shared_rsa", rsa_folder)
            message = int.from_bytes(rsa_plaintext, "big")
            self.assertTrue(all("modulus" not in sample for sample in rsa_doc["samples"]))
            for index in rsa["matching_indexes"]:
                sample = rsa_doc["samples"][index]
                self.assertEqual(
                    sample["ciphertext"],
                    pow(message + sample["offset"], 3, rsa_doc["modulus"]),
                )

            vm_folder = root / "byte_machine-r1" / "untrusted"
            vm_doc = json.loads((vm_folder / "program.json").read_text())
            vm_plaintext, _ = suite.reference_decode_instance("byte_machine", vm_folder)
            for opcode in vm_doc["opcodes"]:
                for value in range(256):
                    encoded = suite._vm_apply(value, 7, 0xA5, opcode)
                    self.assertEqual(suite._vm_reverse(encoded, 7, 0xA5, opcode), value)
            state = vm_doc["initial_state"]
            full_outputs = []
            for index, plain in enumerate(vm_plaintext):
                encoded = plain
                for opcode in vm_doc["opcodes"]:
                    encoded = suite._vm_apply(encoded, index, state, opcode)
                full_outputs.append(encoded)
                state = suite._vm_next_state(
                    state, plain, encoded, index, vm_doc["state_update"]
                )
            observed = bytes.fromhex(vm_doc["observed_low6"])
            self.assertEqual(bytes(value & 0x3F for value in full_outputs), observed)
            self.assertTrue(any(value > 0x3F for value in full_outputs))
            self.assertEqual(state, vm_doc["final_state"])

            fragment_folder = root / "fragment_log-r1" / "untrusted"
            rows = [json.loads(line) for line in (fragment_folder / "capture.jsonl").read_text().splitlines()]
            metadata = next(row for row in rows if row.get("event") == "start")
            fragment_plaintext, fragment = suite.reference_decode_instance("fragment_log", fragment_folder)
            compressed = zlib.compress(fragment_plaintext, level=9)
            parts = [
                compressed[index : index + metadata["chunk_size"]]
                for index in range(0, len(compressed), metadata["chunk_size"])
            ]
            parity_rows = {
                row["kind"]: base64.b64decode(row["data"])
                for row in rows
                if row.get("event") == "parity" and row.get("transfer") == metadata["transfer"]
            }
            self.assertEqual(len(fragment["missing_sequences"]), 2)
            self.assertEqual(
                parity_rows["xor"], suite._xor_padded(parts, metadata["chunk_size"])
            )
            self.assertEqual(
                parity_rows["gf256"],
                suite._gf256_parity(parts, metadata["coefficients"], metadata["chunk_size"]),
            )

    def test_gf256_arithmetic_and_two_erasure_equations(self):
        self.assertEqual(suite._gf256_mul(0x57, 0x13), 0xFE)
        for value in range(1, 256):
            self.assertEqual(suite._gf256_mul(value, suite._gf256_inverse(value)), 1)
        left, right = 0xA6, 0x3D
        left_coefficient, right_coefficient = 0x17, 0xC2
        parity_p = left ^ right
        parity_q = (
            suite._gf256_mul(left_coefficient, left)
            ^ suite._gf256_mul(right_coefficient, right)
        )
        recovered_left = suite._gf256_mul(
            suite._gf256_inverse(left_coefficient ^ right_coefficient),
            parity_q ^ suite._gf256_mul(right_coefficient, parity_p),
        )
        self.assertEqual(recovered_left, left)
        self.assertEqual(parity_p ^ recovered_left, right)

    def test_vm_order_and_constants_vary_by_instance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "suite"
            suite.generate(root, 4, SEED_A, tasks=["byte_machine"])
            programs = [
                json.loads((root / f"byte_machine-r{repeat}" / "untrusted" / "program.json").read_text())
                for repeat in range(1, 5)
            ]
            orders = {tuple(op["op"] for op in program["opcodes"]) for program in programs}
            constants = {json.dumps(program["state_update"], sort_keys=True) for program in programs}
            self.assertGreater(len(orders), 1)
            self.assertEqual(len(constants), 4)

    def test_answer_key_and_outputs_contain_no_seed_plaintext_or_solver(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "suite"
            manifest = suite.generate(root, 1, SEED_A)
            answer = (root / "answer-key.json").read_bytes()
            self.assertNotIn(SEED_A, answer)
            self.assertNotIn(SEED_A.hex().encode("ascii"), answer.lower())
            self.assertNotIn(b"BENCH{", answer)
            self.assertFalse(any(path.suffix == ".py" for path in root.rglob("*")))
            self.assertFalse(any("generator" in path.name.lower() or "reference" in path.name.lower() for path in root.rglob("*")))
            all_output = b"\n".join(path.read_bytes() for path in root.rglob("*") if path.is_file())
            self.assertNotIn(SEED_A, all_output)
            self.assertNotIn(SEED_A.hex().encode("ascii"), all_output.lower())
            for task_id, entry in manifest.items():
                _, flag_key = suite.derive_instance_material(SEED_A, "main", entry["task"], entry["repeat"])
                flag = suite._flag(flag_key)
                self.assertEqual(hashlib.sha256(flag).hexdigest(), entry["flag_sha256"])
                self.assertNotIn(flag, all_output)

    def test_reference_decoders_across_multiple_seeds(self):
        for index, seed in enumerate((SEED_A, SEED_B, hashlib.sha256(b"third-seed").digest())):
            with self.subTest(seed=index), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "suite"
                manifest = suite.generate(root, 2, seed, "unseen", tasks=sorted(suite.HARD_TASKS))
                for task in sorted(suite.HARD_TASKS):
                    for repeat in (1, 2):
                        flag, _ = suite.reference_decode_instance(task, root / f"{task}-r{repeat}" / "untrusted")
                        self.assertRegex(flag.decode("ascii"), r"\ABENCH\{[0-9a-f]{32}\}\Z")
                        self.assertEqual(hashlib.sha256(flag).hexdigest(), manifest[f"{task}-r{repeat}"]["flag_sha256"])

    def test_full_generation_is_feasible_under_twenty_seconds(self):
        with tempfile.TemporaryDirectory() as temporary:
            started = time.monotonic()
            suite.generate(Path(temporary) / "suite", 2, SEED_A)
            self.assertLess(time.monotonic() - started, 20.0)

    def test_cli_accepts_seed_file_without_echoing_seed(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            seed_file = base / "seed.bin"
            seed_file.write_bytes(SEED_A)
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(ROOT / "benchmarks" / "make_suite.py"),
                    str(base / "suite"),
                    "--repeats",
                    "1",
                    "--domain",
                    "main",
                    "--tasks",
                    "lcg_stream",
                    "--master-seed-file",
                    str(seed_file),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=20,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            combined = (result.stdout + result.stderr).lower()
            self.assertNotIn(SEED_A.hex(), combined)
            report = json.loads(result.stdout)
            self.assertEqual(report["instances"], 1)
            self.assertEqual(report["suite_version"], 3)


if __name__ == "__main__":
    unittest.main()
