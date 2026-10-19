"""Re-run model scripts in a networkless bwrap namespace inside ubuntu-ctf.

Only the submitted solve.py is copied. Neither answer keys, original work outputs,
home credentials, repository nor other trials are mounted into the namespace.
"""
import argparse
import hashlib
import json
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


FLAG_RE = re.compile(rb"BENCH\{[0-9a-f]{32}\}")
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def limits():
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    resource.setrlimit(resource.RLIMIT_FSIZE, (10_000_000, 10_000_000))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_AS, (1_500_000_000, 1_500_000_000))


def execution_summary(returncode, stdout=b"", stderr=b""):
    """Return bounded verification evidence without returning either stream."""
    stdout = bytes(stdout)
    stderr = bytes(stderr)
    candidates = FLAG_RE.findall(stdout)
    candidate_hashes = sorted({hashlib.sha256(candidate).hexdigest() for candidate in candidates})
    return {
        "returncode": returncode,
        "stdout_bytes": len(stdout),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_bytes": len(stderr),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "candidate_flag_sha256s": candidate_hashes,
        "candidate_flag_count": len(candidates),
    }


def _read_stream(handle):
    handle.flush()
    handle.seek(0)
    return handle.read()


def verify(script, inputs):
    with tempfile.TemporaryDirectory(prefix="ctf-verify-") as temporary:
        work = Path(temporary)
        shutil.copy2(script, work / "solve.py")
        command = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session",
                   "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib",
                   "--ro-bind", "/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev",
                   "--tmpfs", "/tmp", "--dir", "/home", "--dir", "/home/ctf",
                   "--ro-bind", "/home/ctf/.ctf-tools/venv", "/home/ctf/.ctf-tools/venv",
                   "--ro-bind", "/home/ctf/.local/share/uv/python", "/home/ctf/.local/share/uv/python",
                   "--ro-bind", str(inputs.resolve()), "/input", "--bind", temporary, "/work",
                   "--chdir", "/work", "--clearenv", "--setenv", "PATH", "/usr/bin:/bin",
                   "--", "/home/ctf/.ctf-tools/venv/bin/python", "-I", "/work/solve.py", "/input"]
        # Files are bounded by RLIMIT_FSIZE; pipe buffering would ignore that limit.
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            try:
                result = subprocess.run(command, stdout=out, stderr=err, timeout=20, preexec_fn=limits)
                return execution_summary(result.returncode, _read_stream(out), _read_stream(err))
            except subprocess.TimeoutExpired:
                return execution_summary(None, _read_stream(out), _read_stream(err))


def load_suite():
    spec = importlib.util.spec_from_file_location("make_suite", Path(__file__).with_name("make_suite.py"))
    suite = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(suite)
    return suite


def read_seed(path):
    seed = path.read_bytes()
    if len(seed) != 32:
        raise ValueError("Private master seed must contain exactly 32 bytes")
    return seed


def input_commitment(folder, entry):
    hashes = {}
    for path in sorted(folder.rglob("*")):
        if path.is_symlink() or not path.is_file():
            raise ValueError("Unseen input must be a flat regular-file tree")
        hashes[path.relative_to(folder).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if hashes != entry["hashes"]:
        raise ValueError("Generated unseen manifest does not match its inputs")
    canonical = json.dumps(hashes, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return {"hashes": hashes, "input_digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "flag_sha256": entry["flag_sha256"]}


def unseen_commitments(seed_file, repeats, tasks):
    seed, suite = read_seed(seed_file), load_suite()
    with tempfile.TemporaryDirectory(prefix="ctf-unseen-") as temporary:
        destination = Path(temporary) / "suite"
        manifest = suite.generate(destination, repeats, seed, domain="unseen", tasks=tasks)
        return {instance: input_commitment(destination / instance / "untrusted", entry)
                for instance, entry in manifest.items()}


def verify_instance(work, first, instance, seed_file):
    task, repeat_text = instance.rsplit("-r", 1)
    repeat = int(repeat_text)
    if repeat < 1:
        raise ValueError("Instance repeat must be positive")
    seed, suite = read_seed(seed_file), load_suite()
    one = verify(work / "solve.py", first)
    # Only the trusted verifier sees seed/generator. The submitted script sees
    # one read-only input directory in a separate networkless namespace.
    with tempfile.TemporaryDirectory(prefix="ctf-unseen-") as temporary:
        destination = Path(temporary) / "suite"
        manifest = suite.generate(destination, repeat, seed, domain="unseen", tasks=[task])
        folder = destination / instance / "untrusted"
        commitment = input_commitment(folder, manifest[instance])
        two = verify(work / "solve.py", folder)
    return {"status": "ran", "same_execution": one, "new_execution": two,
            "unseen_hashes": commitment["hashes"], "unseen_input_digest": commitment["input_digest"],
            "new_expected_flag_sha256": commitment["flag_sha256"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--master-seed-file", required=True, type=Path)
    parser.add_argument("--commitments", action="store_true")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--tasks", nargs="+")
    parser.add_argument("--work", type=Path)
    parser.add_argument("--first", type=Path)
    parser.add_argument("--instance")
    args = parser.parse_args()
    if args.commitments:
        result = unseen_commitments(args.master_seed_file, args.repeats, args.tasks)
    else:
        if not args.work or not args.first or not args.instance:
            parser.error("Verification requires --work, --first and --instance")
        result = verify_instance(args.work, args.first, args.instance, args.master_seed_file)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
