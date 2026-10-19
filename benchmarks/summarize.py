"""Aggregate native CLI trials without hiding infra failures or missing cells."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import hmac
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import statistics
import subprocess

RUBRIC = {"hypothesis", "commands", "observations", "writeup"}
COMPLIANCE = {"external_access", "host_execution", "extra_model", "background_process", "cross_trial_access"}
PROTOCOL_VERSION = 6
SUITE_VERSION = 3
TOTAL_BUDGET_SECONDS = 240
ARMS = ["claude_raw", "codex_raw", "project_harness"]
ARM_METADATA = {
    "claude_raw": {"provider": "claude", "condition": "raw"},
    "codex_raw": {"provider": "codex", "condition": "raw"},
    "project_harness": {"provider": "claude+codex", "condition": "harness"},
}
PHASE_PLANS = {
    "claude_raw": [("claude_solve", "claude", 240)],
    "codex_raw": [("codex_solve", "codex", 240)],
    "project_harness": [("claude_solve", "claude", 120), ("codex_review", "codex", 60),
                        ("claude_finalize", "claude", 60)],
}
PROVIDER_EXECUTION = {
    "claude": {
        "permission_mode": "dontAsk",
        "tools": ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "Skill"],
        "allowed_tools": ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "Skill"],
    },
    "codex": {
        "sandbox": "danger-full-access",
        "approval_policy": "never",
        "reason": "required-for-ubuntu-ctf-wsl-access",
    },
    "nested_model_calls": {
        "guard": "command-name-deny-shims",
        "trace": "phase-stdout-stderr-preserved",
        "limitation": "not-an-os-sandbox-or-absolute-path-block",
    },
    "codex_review": {
        "policy": "read-only",
        "enforcement": "trial-tree-hashes-before-and-after",
        "mutation_response": "critical-integrity-error-stop-preserve-active",
    },
}

MASTER_SEED_PATH = Path(".private/master-seed.bin")
PROTOCOL_HMAC_FIELD = "protocol_hmac_sha256"
PROTOCOL_HMAC_DOMAIN = b"ctf-benchmark/protocol-v6/protocol-hmac-key\0"
RESULT_HMAC_FIELD = "result_hmac_sha256"
RESULT_HMAC_DOMAIN = b"ctf-benchmark/protocol-v6/result-hmac-key\0"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
SAFE_EXECUTION_FIELDS = {
    "returncode", "stdout_bytes", "stdout_sha256", "stderr_bytes", "stderr_sha256",
    "candidate_flag_count", "candidate_flag_sha256s",
}
VERIFIER_PROCESS_FIELDS = {
    "returncode", "stdout_bytes", "stdout_sha256", "stderr_bytes", "stderr_sha256",
}
VERIFICATION_FIELDS = {
    "status", "same_instance", "new_instance", "same_execution", "new_execution",
    "unseen_hashes", "unseen_input_digest", "new_expected_flag_sha256",
    "expected_unseen_hashes", "expected_unseen_input_digest", "expected_unseen_flag_sha256",
    "unseen_hashes_match", "unseen_digest_match", "unseen_flag_hash_match",
    "unseen_commitment_match", "verifier_process", "error_type",
}
ALLOWED_VERIFICATION_ERRORS = {
    "Regenerated unseen input or flag commitment does not match the protocol",
}
FLAG_RE = re.compile(r"BENCH\{[0-9a-f]{32}\}")


def phase_protocol():
    return {arm: [{"name": name, "provider": provider, "cap_seconds": cap,
                   "read_only": name == "codex_review"}
                  for name, provider, cap in plan]
            for arm, plan in PHASE_PLANS.items()}


def is_sha256(value):
    return (isinstance(value, str) and len(value) == 64
            and all(character in "0123456789abcdef" for character in value))


def canonical_json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def canonical_sha256(value):
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _is_link_or_reparse(path, info=None):
    info = path.lstat() if info is None else info
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def require_plain_file(path, label):
    try:
        info = path.lstat()
    except OSError as error:
        raise ValueError(f"Missing {label}: {path}") from error
    if _is_link_or_reparse(path, info) or not stat.S_ISREG(info.st_mode):
        raise ValueError(f"{label} must be a regular non-linked file: {path}")
    return path


def require_plain_directory(path, label):
    try:
        info = path.lstat()
    except OSError as error:
        raise ValueError(f"Missing {label}: {path}") from error
    if _is_link_or_reparse(path, info) or not stat.S_ISDIR(info.st_mode):
        raise ValueError(f"{label} must be a regular non-linked directory: {path}")
    return path


def plain_entries(directory):
    """Walk a tree without following symlinks, junctions or special files."""
    require_plain_directory(directory, "artifact tree")

    def visit(path):
        info = path.lstat()
        if _is_link_or_reparse(path, info):
            raise ValueError(f"Linked/reparse artifact rejected: {path}")
        if stat.S_ISDIR(info.st_mode):
            yield path, True
            for child in sorted(path.iterdir(), key=lambda item: item.name):
                yield from visit(child)
        elif stat.S_ISREG(info.st_mode):
            yield path, False
        else:
            raise ValueError(f"Non-regular artifact rejected: {path}")

    yield from visit(directory)


def tree_hashes(directory):
    hashes = {}
    for path, is_directory in plain_entries(directory):
        if path == directory:
            continue
        relative = path.relative_to(directory).as_posix()
        if is_directory:
            hashes[relative + "/"] = hashlib.sha256(b"directory").hexdigest()
        else:
            hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def benchmark_code_hashes(directory=None):
    directory = Path(__file__).resolve().parent if directory is None else Path(directory)
    require_plain_directory(directory, "benchmark source directory")
    hashes = {}
    for path in sorted((entry for entry in directory.iterdir() if entry.suffix == ".py"),
                       key=lambda entry: entry.name):
        require_plain_file(path, "benchmark source")
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def validate_benchmark_code_hashes(protocol):
    expected = protocol.get("benchmark_code_hashes")
    if (not isinstance(expected, dict) or not expected
            or any(not isinstance(name, str) or not name.endswith(".py") or "/" in name
                   or "\\" in name or not is_sha256(digest)
                   for name, digest in expected.items())):
        raise ValueError("Protocol benchmark code hashes are missing or invalid")
    if expected != benchmark_code_hashes():
        raise ValueError("Benchmark source files do not match the protocol")


def derive_result_hmac_key(master_seed):
    if not isinstance(master_seed, bytes) or len(master_seed) != 32:
        raise ValueError("Private master seed must contain exactly 32 bytes")
    return hmac.new(master_seed, RESULT_HMAC_DOMAIN, hashlib.sha256).digest()


def derive_protocol_hmac_key(master_seed):
    if not isinstance(master_seed, bytes) or len(master_seed) != 32:
        raise ValueError("Private master seed must contain exactly 32 bytes")
    return hmac.new(master_seed, PROTOCOL_HMAC_DOMAIN, hashlib.sha256).digest()


def compute_result_hmac(row, key):
    payload = dict(row)
    payload.pop(RESULT_HMAC_FIELD, None)
    return hmac.new(key, canonical_json_bytes(payload), hashlib.sha256).hexdigest()


def compute_protocol_hmac(protocol, key):
    payload = dict(protocol)
    payload.pop(PROTOCOL_HMAC_FIELD, None)
    return hmac.new(key, canonical_json_bytes(payload), hashlib.sha256).hexdigest()


def read_master_seed(root):
    private = require_plain_directory(root / MASTER_SEED_PATH.parent, "private seed directory")
    entries = list(private.iterdir())
    if len(entries) != 1 or entries[0].name != MASTER_SEED_PATH.name:
        raise ValueError("Private seed directory contains unexpected entries")
    seed = require_plain_file(root / MASTER_SEED_PATH, "private master seed").read_bytes()
    if len(seed) != 32:
        raise ValueError("Private master seed must contain exactly 32 bytes")
    return seed


def authenticate_protocol(root, protocol):
    """Authenticate the complete plan before trusting any field inside it."""
    if not isinstance(protocol, dict):
        raise ValueError("Protocol must be an object")
    seed = read_master_seed(root)
    supplied = protocol.get(PROTOCOL_HMAC_FIELD)
    expected = compute_protocol_hmac(protocol, derive_protocol_hmac_key(seed))
    if not is_sha256(supplied) or not hmac.compare_digest(supplied, expected):
        raise ValueError("Protocol HMAC mismatch")
    if hashlib.sha256(seed).hexdigest() != protocol.get("master_seed_sha256"):
        raise ValueError("Private master seed does not match the protocol commitment")
    return seed


def wsl_path(path):
    value = str(Path(path).resolve()).replace("\\", "/")
    if len(value) < 3 or value[1:3] != ":/" or not value[0].isalpha():
        raise ValueError("Benchmark root must be a Windows drive path accessible in WSL")
    return "/mnt/" + value[0].lower() + value[2:]


def regenerate_unseen_commitments(root, protocol):
    """Regenerate the private unseen manifest in WSL without retaining inputs."""
    verifier = Path(__file__).resolve().with_name("verify_solution.py")
    command = ["wsl", "-d", "ubuntu-ctf", "--", "/home/ctf/.ctf-tools/venv/bin/python",
               "-I", wsl_path(verifier), "--commitments", "--master-seed-file",
               wsl_path(root / MASTER_SEED_PATH), "--repeats", str(protocol["repeats"]),
               "--tasks", *protocol["tasks"]]
    try:
        response = subprocess.run(command, text=True, encoding="utf-8", errors="replace",
                                  capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError("Unseen commitment regeneration failed") from error
    if response.returncode:
        raise ValueError("Unseen commitment regeneration failed")
    try:
        regenerated = json.loads(response.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("Unseen commitment regeneration returned invalid JSON") from error
    if not isinstance(regenerated, dict):
        raise ValueError("Unseen commitment regeneration returned a non-object")
    return regenerated


def load_main_answer_hashes(root, protocol, expected_instances):
    suite_hashes = protocol.get("suite_hashes")
    if (not isinstance(suite_hashes, dict) or not suite_hashes
            or any(not isinstance(name, str) or not is_sha256(digest)
                   for name, digest in suite_hashes.items())):
        raise ValueError("Protocol suite hashes are missing or invalid")
    suite = root / "suite"
    if tree_hashes(suite) != suite_hashes:
        raise ValueError("Prepared suite does not match the protocol")
    answer_path = require_plain_file(suite / "answer-key.json", "suite answer key")
    try:
        answer_key = json.loads(answer_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Suite answer key is invalid") from error
    if not isinstance(answer_key, dict) or set(answer_key) != set(expected_instances):
        raise ValueError("Suite answer key instances do not match the protocol")
    hashes = {}
    for instance, entry in answer_key.items():
        if not isinstance(entry, dict) or not is_sha256(entry.get("flag_sha256")):
            raise ValueError(f"Invalid suite answer key entry: {instance}")
        hashes[instance] = entry["flag_sha256"]
    return hashes


def validate_originals_unchanged(root, archive, instance, claimed):
    """Recompute the result bit from the archived and prepared untrusted trees."""
    prepared = root / "suite" / instance / "untrusted"
    archived = archive / "events" / "local-benchmark" / "challenges" / instance / "untrusted"
    prepared_hashes = tree_hashes(prepared)
    try:
        archived.lstat()
    except FileNotFoundError:
        unchanged = False
    else:
        unchanged = tree_hashes(archived) == prepared_hashes
    if claimed != unchanged:
        raise ValueError(f"Originals integrity result disagrees with archived evidence: {instance}")
    return unchanged


def is_relative_posix_file(value):
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return (path.as_posix() == value and not path.is_absolute() and ".." not in path.parts
            and not PureWindowsPath(value).is_absolute())


def wilson(successes, total):
    if not total:
        return [None, None]
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z*z/total
    center = (p + z*z/(2*total))/denominator
    margin = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total))/denominator
    return [round(max(0, center-margin), 4), round(min(1, center+margin), 4)]


def usage_totals(provider, rows):
    """Keep provider conventions explicit and missing usage distinct from zero."""
    available = [r["usage"] for r in rows if isinstance(r.get("usage", {}).get("input_tokens"), int)
                 and isinstance(r.get("usage", {}).get("output_tokens"), int)]
    if not available:
        return {"reported_trials": 0, "missing_trials": len(rows), "prompt_tokens": None,
                "output_tokens": None, "cache_read_tokens": None, "cache_write_tokens": None}
    if provider == "claude":
        cache_read = sum(u.get("cache_read_input_tokens", 0) for u in available)
        cache_write = sum(u.get("cache_creation_input_tokens", 0) for u in available)
        prompt = sum(u["input_tokens"] for u in available) + cache_read + cache_write
        convention = "Claude input + cache_read_input + cache_creation_input; output as reported"
    else:
        cache_read = sum(u.get("cached_input_tokens", 0) for u in available)
        cache_write = sum(u.get("cache_write_input_tokens", 0) for u in available)
        prompt = sum(u["input_tokens"] for u in available)
        convention = "Codex input total as reported; cached tokens are not added again; output as reported"
    return {"reported_trials": len(available), "missing_trials": len(rows)-len(available),
            "prompt_tokens": prompt, "output_tokens": sum(u["output_tokens"] for u in available),
            "cache_read_tokens": cache_read, "cache_write_tokens": cache_write, "convention": convention}


def phase_usage_totals(rows):
    """Aggregate usage by provider without treating a three-phase team as one provider."""
    buckets = {"claude": [], "codex": []}
    for row in rows:
        for phase in row.get("phases", []):
            provider = phase.get("provider")
            if provider in buckets and phase.get("process_started") is True:
                buckets[provider].append({"usage": phase.get("usage", {})})
    return {provider: usage_totals(provider, phases) for provider, phases in buckets.items() if phases}


def validate_protocol(protocol):
    if not isinstance(protocol, dict):
        raise ValueError("Protocol must be an object")
    if protocol.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError(f"Protocol version must be {PROTOCOL_VERSION}")
    if protocol.get("suite_version") != SUITE_VERSION:
        raise ValueError(f"Suite version must be {SUITE_VERSION}")
    if not is_sha256(protocol.get("master_seed_sha256")):
        raise ValueError("Protocol master_seed_sha256 must be 64 lowercase hex characters")
    if protocol.get("arms") != ARMS:
        raise ValueError("Protocol arms do not match the fixed three-arm experiment")
    if protocol.get("phase_plans") != phase_protocol():
        raise ValueError("Protocol phase plans do not match the fixed workflow")
    if protocol.get("provider_execution") != PROVIDER_EXECUTION:
        raise ValueError("Protocol provider execution policy does not match version 6")
    if protocol.get("timeout") != TOTAL_BUDGET_SECONDS:
        raise ValueError(f"Protocol timeout must be {TOTAL_BUDGET_SECONDS} seconds")
    if (not isinstance(protocol.get("claude_model"), str) or not protocol["claude_model"].strip()
            or not isinstance(protocol.get("codex_model"), str) or not protocol["codex_model"].strip()):
        raise ValueError("Protocol must name both requested models")
    tasks = protocol.get("tasks")
    repeats = protocol.get("repeats")
    workers = protocol.get("workers")
    if (not isinstance(tasks, list) or not tasks or any(not isinstance(task, str) or not task for task in tasks)
            or len(set(tasks)) != len(tasks)):
        raise ValueError("Protocol tasks must be a non-empty unique list")
    if type(repeats) is not int or repeats < 1:
        raise ValueError("Protocol repeats must be a positive integer")
    if type(workers) is not int or workers not in {1, 2}:
        raise ValueError("Protocol workers must be one or two")
    specs = protocol.get("specs")
    if not isinstance(specs, list):
        raise ValueError("Protocol specs must be a list")
    identifiers = [spec.get("id") for spec in specs if isinstance(spec, dict)]
    if len(identifiers) != len(specs) or len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate or invalid trial ids in protocol")
    expected = {}
    cells = set()
    by_instance = defaultdict(list)
    for spec in specs:
        identifier = spec.get("id")
        arm = spec.get("arm")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("Invalid trial id in protocol")
        if arm not in ARMS:
            raise ValueError(f"Unknown protocol arm: {arm}")
        if (not isinstance(spec.get("task"), str) or not spec["task"]
                or not isinstance(spec.get("instance"), str) or not spec["instance"]
                or type(spec.get("repeat")) is not int or spec["repeat"] < 1):
            raise ValueError(f"Incomplete protocol metadata: {identifier}")
        if any(spec.get(field) != value for field, value in ARM_METADATA[arm].items()):
            raise ValueError(f"Protocol arm metadata mismatch: {identifier}")
        if identifier != f"{arm}-{spec['instance']}":
            raise ValueError(f"Protocol trial id does not match arm/instance: {identifier}")
        cell = (arm, spec["instance"])
        if cell in cells:
            raise ValueError(f"Duplicate arm/instance cell in protocol: {identifier}")
        cells.add(cell)
        by_instance[spec["instance"]].append(spec)
        expected[identifier] = spec
    expected_inputs = {(task, repeat) for task in tasks for repeat in range(1, repeats + 1)}
    observed_inputs = {(entries[0]["task"], entries[0]["repeat"]) for entries in by_instance.values()}
    if observed_inputs != expected_inputs or len(by_instance) != len(expected_inputs):
        raise ValueError("Protocol instances do not match tasks/repeats")
    for instance, entries in by_instance.items():
        if ({entry["arm"] for entry in entries} != set(ARMS) or len(entries) != len(ARMS)
                or any((entry["task"], entry["repeat"]) !=
                       (entries[0]["task"], entries[0]["repeat"]) for entry in entries)
                or instance != f"{entries[0]['task']}-r{entries[0]['repeat']}"):
            raise ValueError(f"Incomplete or inconsistent three-arm protocol cell: {instance}")
    commitments = protocol.get("unseen_commitments")
    if not isinstance(commitments, dict) or set(commitments) != set(by_instance):
        raise ValueError("Protocol unseen commitments must cover every instance exactly")
    for instance, commitment in commitments.items():
        if not isinstance(commitment, dict) or set(commitment) != {"hashes", "input_digest", "flag_sha256"}:
            raise ValueError(f"Invalid unseen commitment schema: {instance}")
        hashes = commitment["hashes"]
        if (not isinstance(hashes, dict) or not hashes
                or any(not is_relative_posix_file(name) or not is_sha256(digest)
                       for name, digest in hashes.items())):
            raise ValueError(f"Invalid unseen input hashes: {instance}")
        if (not is_sha256(commitment["input_digest"])
                or commitment["input_digest"] != canonical_sha256(hashes)
                or not is_sha256(commitment["flag_sha256"])):
            raise ValueError(f"Tampered unseen commitment: {instance}")
    commitments_digest = protocol.get("unseen_commitments_sha256")
    if (not is_sha256(commitments_digest)
            or commitments_digest != canonical_sha256(commitments)):
        raise ValueError("Protocol unseen commitments digest does not match commitments")
    return expected


def validate_safe_execution(identifier, label, evidence):
    if not isinstance(evidence, dict) or set(evidence) != SAFE_EXECUTION_FIELDS:
        raise ValueError(f"Invalid safe execution evidence: {identifier}/{label}")
    returncode = evidence["returncode"]
    if returncode is not None and type(returncode) is not int:
        raise ValueError(f"Invalid execution return code: {identifier}/{label}")
    for field in ["stdout_bytes", "stderr_bytes", "candidate_flag_count"]:
        if type(evidence[field]) is not int or evidence[field] < 0:
            raise ValueError(f"Invalid execution count: {identifier}/{label}/{field}")
    if not is_sha256(evidence["stdout_sha256"]) or not is_sha256(evidence["stderr_sha256"]):
        raise ValueError(f"Invalid execution stream digest: {identifier}/{label}")
    for stream in ["stdout", "stderr"]:
        if evidence[f"{stream}_bytes"] == 0 and evidence[f"{stream}_sha256"] != EMPTY_SHA256:
            raise ValueError(f"Empty execution stream has a non-empty digest: {identifier}/{label}/{stream}")
    candidates = evidence["candidate_flag_sha256s"]
    if (not isinstance(candidates, list) or any(not is_sha256(value) for value in candidates)
            or candidates != sorted(set(candidates))
            or evidence["candidate_flag_count"] < len(candidates)
            or (evidence["candidate_flag_count"] == 0) != (not candidates)):
        raise ValueError(f"Invalid candidate flag evidence: {identifier}/{label}")
    return evidence


def validate_verifier_process(identifier, evidence):
    if not isinstance(evidence, dict) or set(evidence) != VERIFIER_PROCESS_FIELDS:
        raise ValueError(f"Invalid verifier process evidence: {identifier}")
    returncode = evidence["returncode"]
    if returncode is not None and type(returncode) is not int:
        raise ValueError(f"Invalid verifier process return code: {identifier}")
    for stream in ["stdout", "stderr"]:
        size = evidence[f"{stream}_bytes"]
        digest = evidence[f"{stream}_sha256"]
        if type(size) is not int or size < 0 or not is_sha256(digest):
            raise ValueError(f"Invalid verifier process stream evidence: {identifier}/{stream}")
        if size == 0 and digest != EMPTY_SHA256:
            raise ValueError(f"Empty verifier process stream has a non-empty digest: {identifier}/{stream}")
    if returncode is None and evidence != empty_verifier_process():
        raise ValueError(f"Unstarted verifier process has non-empty evidence: {identifier}")
    return evidence


def empty_safe_execution():
    return {"returncode": None, "stdout_bytes": 0, "stdout_sha256": EMPTY_SHA256,
            "stderr_bytes": 0, "stderr_sha256": EMPTY_SHA256,
            "candidate_flag_count": 0, "candidate_flag_sha256s": []}


def empty_verifier_process():
    return {"returncode": None, "stdout_bytes": 0, "stdout_sha256": EMPTY_SHA256,
            "stderr_bytes": 0, "stderr_sha256": EMPTY_SHA256}


def execution_matches(evidence, expected_flag_sha256):
    return (evidence["returncode"] == 0 and evidence["candidate_flag_count"] == 1
            and evidence["candidate_flag_sha256s"] == [expected_flag_sha256])


def validate_verification(identifier, row, commitment, same_expected_flag_sha256):
    if row.get("unseen_commitment") != commitment:
        raise ValueError(f"Result unseen commitment mismatch: {identifier}")
    verification = row.get("verification")
    if not isinstance(verification, dict):
        raise ValueError(f"Invalid trial verification: {identifier}")
    status = verification.get("status")
    allowed_fields = VERIFICATION_FIELDS if status == "ran" else VERIFICATION_FIELDS | {"error"}
    if (not VERIFICATION_FIELDS <= set(verification) or not set(verification) <= allowed_fields
            or status not in {"ran", "missing_script", "verification_infrastructure_error", "not_run"}
            or type(verification.get("same_instance")) is not bool
            or type(verification.get("new_instance")) is not bool):
        raise ValueError(f"Invalid verification outcome: {identifier}")
    if "error" in verification and (not isinstance(verification["error"], str)
                                     or verification["error"] not in ALLOWED_VERIFICATION_ERRORS):
        raise ValueError(f"Invalid verification error evidence: {identifier}")
    if (verification.get("expected_unseen_hashes") != commitment["hashes"]
            or verification.get("expected_unseen_input_digest") != commitment["input_digest"]
            or verification.get("expected_unseen_flag_sha256") != commitment["flag_sha256"]):
        raise ValueError(f"Verification expected commitment mismatch: {identifier}")
    same_execution = validate_safe_execution(identifier, "same", verification["same_execution"])
    new_execution = validate_safe_execution(identifier, "new", verification["new_execution"])
    verifier_process = validate_verifier_process(identifier, verification["verifier_process"])
    error_type = verification["error_type"]
    if error_type is not None and (not isinstance(error_type, str)
                                   or re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", error_type) is None):
        raise ValueError(f"Invalid verification error type: {identifier}")
    match_fields = ["unseen_digest_match", "unseen_flag_hash_match", "unseen_commitment_match"]
    match_fields.append("unseen_hashes_match")
    if any(type(verification.get(field)) is not bool for field in match_fields):
        raise ValueError(f"Invalid verification commitment flags: {identifier}")
    hashes = verification["unseen_hashes"]
    digest = verification["unseen_input_digest"]
    flag_hash = verification["new_expected_flag_sha256"]
    observed = bool(hashes) or digest is not None or flag_hash is not None
    if observed:
        if (not isinstance(hashes, dict) or not hashes
                or any(not is_relative_posix_file(name) or not is_sha256(value)
                       for name, value in hashes.items())
                or not is_sha256(digest) or digest != canonical_sha256(hashes)
                or not is_sha256(flag_hash)):
            raise ValueError(f"Invalid verification commitment evidence: {identifier}")
        hashes_match = hashes == commitment["hashes"]
        digest_match = digest == commitment["input_digest"]
        flag_match = flag_hash == commitment["flag_sha256"]
        combined_match = hashes_match and digest_match and flag_match
    else:
        if hashes != {} or digest is not None or flag_hash is not None:
            raise ValueError(f"Incomplete verification commitment evidence: {identifier}")
        hashes_match = digest_match = flag_match = combined_match = False
    expected_flags = {"unseen_hashes_match": hashes_match,
                      "unseen_digest_match": digest_match,
                      "unseen_flag_hash_match": flag_match,
                      "unseen_commitment_match": combined_match}
    if any(verification[field] != value for field, value in expected_flags.items()):
        raise ValueError(f"Inconsistent verification commitment flags: {identifier}")

    verifier_ok = status == "ran" and verifier_process["returncode"] == 0
    same_success = verifier_ok and execution_matches(same_execution, same_expected_flag_sha256)
    new_success = (verifier_ok and combined_match
                   and execution_matches(new_execution, commitment["flag_sha256"]))
    if (verification["same_instance"] != same_success
            or verification["new_instance"] != new_success):
        raise ValueError(f"Verification success flags disagree with safe evidence: {identifier}")

    if status == "ran":
        if not observed or not combined_match or error_type is not None or "error" in verification:
            raise ValueError(f"Invalid ran verification outcome: {identifier}")
    elif status in {"missing_script", "not_run"}:
        if (observed or same_execution != empty_safe_execution()
                or new_execution != empty_safe_execution()
                or verifier_process != empty_verifier_process()
                or error_type is not None or "error" in verification):
            raise ValueError(f"Non-ran verification must contain only safe empty evidence: {identifier}")
    else:
        coherent_mismatch = (verification.get("error") in ALLOWED_VERIFICATION_ERRORS
                             and observed and not combined_match and error_type is None
                             and verifier_process["returncode"] is not None)
        caught_error = ("error" not in verification and not observed
                        and same_execution == empty_safe_execution()
                        and new_execution == empty_safe_execution()
                        and error_type is not None)
        if not (coherent_mismatch or caught_error):
            raise ValueError(f"Invalid verification infrastructure evidence: {identifier}")


def reproducible_success(row):
    verification = row["verification"]
    return (row["correct"] and verification["status"] == "ran"
            and verification["same_instance"] is True
            and verification["new_instance"] is True
            and verification["unseen_commitment_match"] is True)


def load_results(root, protocol, *, commitment_regenerator=None):
    seed = authenticate_protocol(root, protocol)
    expected = validate_protocol(protocol)
    validate_benchmark_code_hashes(protocol)
    regenerated = (commitment_regenerator or regenerate_unseen_commitments)(root, protocol)
    if regenerated != protocol["unseen_commitments"]:
        raise ValueError("Regenerated unseen commitments do not match the protocol")
    main_answer_hashes = load_main_answer_hashes(
        root, protocol, {spec["instance"] for spec in expected.values()})
    result_key = derive_result_hmac_key(seed)
    results = []
    result_directory = root / "results"
    try:
        result_directory.lstat()
    except FileNotFoundError:
        return results
    require_plain_directory(result_directory, "results directory")
    result_paths = sorted(result_directory.iterdir(), key=lambda item: item.name)
    trials_directory = None
    if result_paths:
        trials_directory = require_plain_directory(root / "trials", "trials directory")
    for path in result_paths:
        if path.suffix != ".json":
            raise ValueError(f"Unexpected entry in results directory: {path.name}")
        require_plain_file(path, "result")
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid result JSON: {path.name}") from error
        if not isinstance(row, dict):
            raise ValueError(f"Result must be an object: {path.name}")
        supplied_hmac = row.get(RESULT_HMAC_FIELD)
        if (not is_sha256(supplied_hmac)
                or not hmac.compare_digest(supplied_hmac, compute_result_hmac(row, result_key))):
            raise ValueError(f"Result HMAC mismatch: {path.name}")
        identifier = row.get("id")
        if identifier not in expected or path.stem != identifier:
            raise ValueError(f"Result does not match a planned trial: {path.name}")
        expected_archive_path = f"trials/{identifier}"
        if row.get("archive_path") != expected_archive_path:
            raise ValueError(f"Result archive path mismatch: {identifier}")
        archive = trials_directory / identifier
        archive_digest = row.get("archive_tree_digest")
        if not is_sha256(archive_digest) or canonical_sha256(tree_hashes(archive)) != archive_digest:
            raise ValueError(f"Result archive tree mismatch: {identifier}")
        for field in ["arm", "provider", "condition", "instance", "task", "repeat"]:
            if row.get(field) != expected[identifier].get(field):
                raise ValueError(f"Result metadata mismatch: {identifier}/{field}")
        arm = row.get("arm")
        if arm not in ARMS:
            raise ValueError(f"Unknown benchmark arm: {identifier}/{arm}")
        if (type(row.get("correct")) is not bool or type(row.get("timeout")) is not bool
                or type(row.get("turn_completed")) is not bool
                or not isinstance(row.get("final"), str)):
            raise ValueError(f"Non-boolean outcome: {identifier}")
        if row.get("status") not in {"completed", "timeout", "infrastructure_error", "cancelled"}:
            raise ValueError(f"Invalid trial status: {identifier}")
        if row.get("timeout") != (row.get("status") == "timeout"):
            raise ValueError(f"Inconsistent trial timeout: {identifier}")
        if row.get("correct") and (row.get("status") != "completed" or row.get("timeout")):
            raise ValueError(f"Nonterminal or timed out trial cannot be correct: {identifier}")
        if row["turn_completed"] != (row["status"] == "completed"):
            raise ValueError(f"Trial completion evidence disagrees with status: {identifier}")
        candidates = sorted({hashlib.sha256(flag.encode("utf-8")).hexdigest()
                             for flag in FLAG_RE.findall(row["final"])})
        mechanical_correct = (row["status"] == "completed" and len(candidates) == 1
                              and candidates == [main_answer_hashes[row["instance"]]])
        if row["correct"] != mechanical_correct:
            raise ValueError(f"Mechanical correctness disagrees with terminal evidence: {identifier}")
        elapsed = row.get("elapsed_seconds")
        if type(elapsed) not in {int, float} or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError(f"Invalid duration: {identifier}")
        if type(row.get("originals_unchanged")) is not bool:
            raise ValueError(f"Invalid originals integrity result: {identifier}")
        validate_originals_unchanged(root, archive, row["instance"], row["originals_unchanged"])
        if (type(row.get("tool_calls")) is not int or row.get("tool_calls") < 0
                or type(row.get("model_calls")) is not int or row.get("model_calls") < 0
                or type(row.get("writeup_present")) is not bool
                or not isinstance(row.get("verification"), dict)):
            raise ValueError(f"Invalid trial evidence metadata: {identifier}")
        validate_verification(identifier, row, protocol["unseen_commitments"][row["instance"]],
                              main_answer_hashes[row["instance"]])
        phases = row.get("phases")
        if not isinstance(phases, list) or len(phases) > len(PHASE_PLANS[arm]):
            raise ValueError(f"Invalid phase list: {identifier}")
        if not phases and row.get("status") != "infrastructure_error":
            raise ValueError(f"Only a pre-launch infrastructure failure may have no phases: {identifier}")
        for phase, (name, provider, cap) in zip(phases, PHASE_PLANS[arm]):
            if (not isinstance(phase, dict) or phase.get("name") != name or phase.get("provider") != provider
                    or phase.get("cap_seconds") != cap):
                raise ValueError(f"Phase protocol mismatch: {identifier}/{name}")
            if (phase.get("requested_model") != protocol[f"{provider}_model"]
                    or type(phase.get("read_only")) is not bool
                    or phase["read_only"] != (name == "codex_review")):
                raise ValueError(f"Phase model or access mismatch: {identifier}/{name}")
            if (type(phase.get("timeout")) is not bool or type(phase.get("process_started")) is not bool
                    or type(phase.get("tool_calls")) is not int
                    or phase.get("tool_calls") < 0
                    or phase.get("status") not in {"completed", "timeout", "infrastructure_error", "cancelled"}):
                raise ValueError(f"Invalid phase outcome: {identifier}/{name}")
            budget = phase.get("budget_seconds")
            if (type(budget) not in {int, float} or not math.isfinite(budget)
                    or budget < 0 or budget > cap
                    or (budget == 0 and (phase.get("status") != "timeout" or phase.get("timeout") is not True))):
                raise ValueError(f"Invalid phase budget: {identifier}/{name}")
            phase_elapsed = phase.get("elapsed_seconds")
            if (type(phase_elapsed) not in {int, float} or not math.isfinite(phase_elapsed)
                    or phase_elapsed < 0
                    or (phase.get("status") != "infrastructure_error" and phase_elapsed > budget + 35)):
                raise ValueError(f"Invalid phase duration: {identifier}/{name}")
            if phase.get("timeout") != (phase.get("status") == "timeout"):
                raise ValueError(f"Inconsistent phase timeout: {identifier}/{name}")
            if (phase.get("status") == "completed" and not phase["process_started"]
                    or not phase["process_started"] and phase["tool_calls"] != 0):
                raise ValueError(f"Invalid phase process state: {identifier}/{name}")
        if row.get("tool_calls") != sum(phase["tool_calls"] for phase in phases):
            raise ValueError(f"Trial tool count does not match phases: {identifier}")
        if row.get("model_calls") != sum(phase["process_started"] for phase in phases):
            raise ValueError(f"Trial model-call count does not match phases: {identifier}")
        if any(phase["timeout"] for phase in phases) and not row.get("timeout"):
            raise ValueError(f"Trial hides a phase timeout: {identifier}")
        if row.get("status") == "completed" and (len(phases) != len(PHASE_PLANS[arm])
                                                   or any(phase["status"] != "completed" for phase in phases)):
            raise ValueError(f"Trial marked completed is missing a completed required phase: {identifier}")
        if row.get("correct") and (len(phases) != len(PHASE_PLANS[arm])
                                   or any(phase["status"] != "completed" for phase in phases)):
            raise ValueError(f"Correct trial is missing a completed required phase: {identifier}")
        results.append(row)
    return results


def load_reviews(root, results):
    path = root / "reviews/evidence.json"
    if not path.exists():
        return {}
    reviews = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(reviews, dict) or not set(reviews) <= {r["id"] for r in results}:
        raise ValueError("Reviews must refer only to observed trial ids")
    for identifier, review in reviews.items():
        if not isinstance(review, dict):
            raise ValueError(f"Review must be an object: {identifier}")
        scores = review.get("scores", {})
        reviewer_scores = review.get("reviewer_scores", {})
        adjudicator_scores = review.get("adjudicator_scores", {})
        evidence = review.get("evidence", {})
        compliance = review.get("compliance", {})
        for label, values in [("agreed", scores), ("reviewer", reviewer_scores),
                              ("adjudicator", adjudicator_scores)]:
            if set(values) != RUBRIC or any(type(v) is not int or v not in {0, 1, 2} for v in values.values()):
                raise ValueError(f"Invalid {label} evidence rubric scores: {identifier}")
        if set(evidence) != RUBRIC or any(not isinstance(v, str) or not v.strip() for v in evidence.values()):
            raise ValueError(f"Each score needs an evidence reference/reason: {identifier}")
        if set(compliance) != COMPLIANCE or any(v not in {"pass", "violation", "unknown"} for v in compliance.values()):
            raise ValueError(f"Incomplete compliance review: {identifier}")
        if (not review.get("reviewer") or not review.get("adjudicator")
                or review["reviewer"] == review["adjudicator"]
                or not isinstance(review.get("adjudication"), str) or not review["adjudication"].strip()):
            raise ValueError(f"Missing independent review record: {identifier}")
    return reviews


def protocol_status(row, reviews):
    if not row["originals_unchanged"]:
        return "violation"
    review = reviews.get(row["id"])
    if review is None:
        return "unreviewed"
    observations = set(review["compliance"].values())
    if "violation" in observations:
        return "violation"
    if "unknown" in observations:
        return "unresolved"
    return "valid"


def aggregate(root, *, commitment_regenerator=None):
    protocol_path = require_plain_file(root / "protocol.json", "protocol")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    results = load_results(root, protocol, commitment_regenerator=commitment_regenerator)
    reviews = load_reviews(root, results)
    result_ids = {row["id"] for row in results}
    primary_metric_ready = (len(results) == len(protocol["specs"])
                            and set(reviews) == result_ids
                            and all("unknown" not in review["compliance"].values()
                                    for review in reviews.values()))
    groups = defaultdict(list)
    plans = defaultdict(int)
    arm_metadata = {}
    for spec in protocol["specs"]:
        arm = spec["arm"]
        if arm not in ARMS:
            raise ValueError(f"Unknown protocol arm: {arm}")
        plans[arm] += 1
        arm_metadata[arm] = ARM_METADATA[arm]
    for row in results:
        groups[row["arm"]].append(row)
    summaries = []
    for arm in ARMS:
        if arm not in plans:
            continue
        planned = plans[arm]
        rows = groups[arm]
        provider = arm_metadata[arm]["provider"]
        condition = arm_metadata[arm]["condition"]
        mechanical_correct = sum(r["correct"] for r in rows)
        reproducible = [r for r in rows if reproducible_success(r)]
        infra = sum(r["status"] == "infrastructure_error" for r in rows)
        mechanical_times = [r["elapsed_seconds"] for r in rows if r["correct"]]
        reproducible_times = [r["elapsed_seconds"] for r in reproducible]
        evidence_scores = [sum(reviews[r["id"]]["scores"].values()) for r in rows if r["id"] in reviews]
        rater_agreements = [reviews[r["id"]]["reviewer_scores"][criterion]
                            == reviews[r["id"]]["adjudicator_scores"][criterion]
                            for r in rows if r["id"] in reviews for criterion in sorted(RUBRIC)]
        statuses = [protocol_status(r, reviews) for r in rows]
        valid = [r for r in rows if protocol_status(r, reviews) == "valid"]
        primary_successes = [r for r in reproducible if protocol_status(r, reviews) == "valid"]
        primary_success_count = len(primary_successes)
        primary_times = [r["elapsed_seconds"] for r in primary_successes]
        summaries.append({"arm": arm, "provider": provider, "condition": condition, "planned": planned,
            "attempts": len(rows), "missing": planned-len(rows),
            "mechanical_flag_correct": mechanical_correct,
            "rate_mechanical_flag_correct_all_attempts": mechanical_correct/len(rows) if rows else None,
            "wilson95_mechanical_descriptive": wilson(mechanical_correct, len(rows)),
            "reproducible_correct": len(reproducible),
            "rate_reproducible_correct_all_attempts": len(reproducible)/len(rows) if rows else None,
            "wilson95_reproducible_descriptive": wilson(len(reproducible), len(rows)),
            "primary_success_count": primary_success_count,
            "primary_metric_ready": primary_metric_ready,
            "primary_success_rate_all_attempts":
                primary_success_count/len(rows) if primary_metric_ready and rows else None,
            "infrastructure_errors": infra, "timeouts": sum(r["timeout"] for r in rows),
            "cancelled": sum(r["status"] == "cancelled" for r in rows),
            "median_seconds_all": statistics.median(r["elapsed_seconds"] for r in rows) if rows else None,
            "median_seconds_mechanical_success_only": statistics.median(mechanical_times) if mechanical_times else None,
            "median_seconds_reproducible_success_only": statistics.median(reproducible_times) if reproducible_times else None,
            "primary_success_median_seconds":
                statistics.median(primary_times) if primary_metric_ready and primary_times else None,
            "tool_calls": sum(r["tool_calls"] for r in rows),
            "writeups_present": sum(r["writeup_present"] for r in rows),
            "scripts_reproduced_same": sum(r["verification"].get("same_instance", False) for r in rows),
            "scripts_reproduced_new": sum(r["verification"].get("new_instance", False) for r in rows),
            "originals_unchanged": sum(r["originals_unchanged"] for r in rows),
            "verification_infrastructure_errors": sum(r["verification"].get("status") == "verification_infrastructure_error" for r in rows),
            "model_calls_observed": sum(p.get("process_started") is True for r in rows for p in r.get("phases", [])),
            "phase_failures": sum(p.get("status") != "completed" for r in rows for p in r.get("phases", [])),
            "token_totals_by_provider": phase_usage_totals(rows),
            "evidence_reviewed": len(evidence_scores),
            "evidence_mean_out_of_8": statistics.mean(evidence_scores) if evidence_scores else None,
            "evidence_rater_exact_agreements": sum(rater_agreements),
            "evidence_rater_comparisons": len(rater_agreements),
            "evidence_rater_exact_agreement_rate": sum(rater_agreements)/len(rater_agreements) if rater_agreements else None,
            "protocol_status_counts": {name: statuses.count(name) for name in ["valid", "violation", "unreviewed", "unresolved"]},
            "primary_success_rate_protocol_valid_only":
                primary_success_count/len(valid) if primary_metric_ready and valid else None,
            "phase_usage_raw": [{"id": r["id"], "phases": [{"name": p["name"], "provider": p["provider"],
                "usage": p.get("usage", {})} for p in r.get("phases", [])]} for r in rows]})
    comparisons = []
    by_id = {(r["arm"], r["instance"]): r for r in results}
    for raw_arm in ["claude_raw", "codex_raw"]:
        mechanical_both, mechanical_raw_only, mechanical_harness_only, mechanical_neither = 0, 0, 0, 0
        reproducible_both, reproducible_raw_only, reproducible_harness_only, reproducible_neither = 0, 0, 0, 0
        valid_both, valid_raw_only, valid_harness_only, valid_neither = 0, 0, 0, 0
        time_deltas, mechanical_both_deltas, primary_both_deltas = [], [], []
        paired_planned_commitments = 0
        paired_observed_digests = 0
        for instance in sorted({r["instance"] for r in results}):
            base = by_id.get((raw_arm, instance))
            harness = by_id.get(("project_harness", instance))
            if not base or not harness:
                continue
            if base["unseen_commitment"] != harness["unseen_commitment"]:
                raise ValueError(f"Paired arms have different unseen commitments: {raw_arm}/{instance}")
            paired_planned_commitments += 1
            base_digest = base["verification"]["unseen_input_digest"]
            harness_digest = harness["verification"]["unseen_input_digest"]
            if (base_digest is not None and harness_digest is not None
                    and base_digest != harness_digest):
                raise ValueError(f"Paired arms used different unseen inputs: {raw_arm}/{instance}")
            if base_digest is not None and harness_digest is not None:
                paired_observed_digests += 1
            b_mechanical, h_mechanical = base["correct"], harness["correct"]
            mechanical_both += b_mechanical and h_mechanical
            mechanical_raw_only += b_mechanical and not h_mechanical
            mechanical_harness_only += h_mechanical and not b_mechanical
            mechanical_neither += not b_mechanical and not h_mechanical
            b_reproducible, h_reproducible = reproducible_success(base), reproducible_success(harness)
            reproducible_both += b_reproducible and h_reproducible
            reproducible_raw_only += b_reproducible and not h_reproducible
            reproducible_harness_only += h_reproducible and not b_reproducible
            reproducible_neither += not b_reproducible and not h_reproducible
            time_deltas.append(harness["elapsed_seconds"] - base["elapsed_seconds"])
            if b_mechanical and h_mechanical:
                mechanical_both_deltas.append(harness["elapsed_seconds"] - base["elapsed_seconds"])
            b_valid = b_reproducible and protocol_status(base, reviews) == "valid"
            h_valid = h_reproducible and protocol_status(harness, reviews) == "valid"
            valid_both += b_valid and h_valid
            valid_raw_only += b_valid and not h_valid
            valid_harness_only += h_valid and not b_valid
            valid_neither += not b_valid and not h_valid
            if b_valid and h_valid:
                primary_both_deltas.append(harness["elapsed_seconds"] - base["elapsed_seconds"])
        n = mechanical_both + mechanical_raw_only + mechanical_harness_only + mechanical_neither
        comparisons.append({"raw_arm": raw_arm, "project_arm": "project_harness",
                      "primary_metric_ready": primary_metric_ready,
                      "pairs": n,
                      "pairs_with_matching_planned_unseen_commitment": paired_planned_commitments,
                      "pairs_with_matching_observed_unseen_digest": paired_observed_digests,
                      "mechanical_both": mechanical_both,
                      "mechanical_raw_only": mechanical_raw_only,
                      "mechanical_harness_only": mechanical_harness_only,
                      "mechanical_neither": mechanical_neither,
                      "mechanical_success_delta_pp_all_pairs":
                          100*(mechanical_harness_only-mechanical_raw_only)/n if n else None,
                      "reproducible_both": reproducible_both,
                      "reproducible_raw_only": reproducible_raw_only,
                      "reproducible_harness_only": reproducible_harness_only,
                      "reproducible_neither": reproducible_neither,
                      "reproducible_success_delta_pp_all_pairs":
                          100*(reproducible_harness_only-reproducible_raw_only)/n if n else None,
                      "primary_success_both": valid_both,
                      "primary_success_raw_only": valid_raw_only,
                      "primary_success_harness_only": valid_harness_only,
                      "primary_success_neither": valid_neither,
                      "primary_success_delta_pp_all_pairs":
                          100*(valid_harness_only-valid_raw_only)/n if primary_metric_ready and n else None,
                      "median_paired_seconds_all_outcomes": statistics.median(time_deltas) if n else None,
                      "mechanical_both_success_time_pairs": len(mechanical_both_deltas),
                      "median_paired_seconds_mechanical_both_success":
                          statistics.median(mechanical_both_deltas) if mechanical_both_deltas else None,
                      "primary_success_both_time_pairs":
                          len(primary_both_deltas) if primary_metric_ready else None,
                      "primary_success_median_paired_seconds_both":
                          statistics.median(primary_both_deltas)
                          if primary_metric_ready and primary_both_deltas else None})
    return {"generated_utc": datetime.now(timezone.utc).isoformat(), "planned": len(protocol["specs"]),
            "observed": len(results), "missing": len(protocol["specs"])-len(results), "groups": summaries,
            "primary_metric_ready": primary_metric_ready, "comparisons": comparisons,
            "limitations": ["Original synthetic educational tasks; not a real CTF distribution.",
                "Repeated task families are correlated; Wilson intervals are descriptive, not population inference.",
                "The project arm changes instructions, reference assets and model workflow together; it measures whole-system uplift, not isolated causality.",
                "Provider system prompts and tool behavior differ; extra project-arm calls, time and tokens are reported as system cost.",
                "The 15-minute pivot effect is not measured by the 240-second trials.",
                "Notes file length and artifact presence are not semantic evidence-quality scores."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = aggregate(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Observed {result['observed']}/{result['planned']} trials; wrote {args.output}")
