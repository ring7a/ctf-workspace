"""Generate deterministic, local-only benchmark challenge data.

The suite is derived from an explicit 256-bit master seed. The seed is never
written to the generated suite, and the hard instances are reference-decoded
before the answer key is committed.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import hmac
import itertools
import json
import math
from pathlib import Path
import random
import re
import zlib


SUITE_VERSION = 3
TASKS = {
    "layered": ("misc", "Recover the flag from the supplied binary message."),
    "repeating_xor": ("crypto", "A short repeating key protected this message. Recover it."),
    "lcg_stream": ("crypto", "Recover a noisy LCG and decrypt the stream."),
    "shared_rsa": ("crypto", "Recover a message from faulty related RSA messages."),
    "byte_machine": ("reverse", "Reverse the data-driven byte machine."),
    "fragment_log": ("forensics", "Recover a damaged transfer from an application capture."),
}
HARD_TASKS = frozenset({"lcg_stream", "shared_rsa", "byte_machine", "fragment_log"})
FLAG_RE = re.compile(rb"BENCH\{[0-9a-f]{32}\}\Z")
_DERIVE_PREFIX = b"ctf-benchmark-suite-v3\0"


def _write_text(path: Path, text: str) -> None:
    """Write stable UTF-8/LF bytes on every host."""
    path.write_bytes(text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8"))


def write_json(path: Path, obj) -> None:
    _write_text(path, json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n")


def _normalise_seed(master_seed: bytes | bytearray | str) -> bytes:
    if isinstance(master_seed, str):
        if not re.fullmatch(r"[0-9a-fA-F]{64}", master_seed):
            raise ValueError("master_seed must be exactly 64 hexadecimal characters")
        seed = bytes.fromhex(master_seed)
    elif isinstance(master_seed, (bytes, bytearray)):
        seed = bytes(master_seed)
    else:
        raise TypeError("master_seed must be 32 bytes or a 64-character hex string")
    if len(seed) != 32:
        raise ValueError("master_seed must contain exactly 256 bits")
    return seed


def _derive(key: bytes, *labels: str) -> bytes:
    encoded = bytearray(_DERIVE_PREFIX)
    for label in labels:
        value = label.encode("utf-8")
        encoded.extend(len(value).to_bytes(4, "big"))
        encoded.extend(value)
    return hmac.new(key, bytes(encoded), hashlib.sha256).digest()


def derive_instance_material(
    master_seed: bytes | bytearray | str, domain: str, task: str, repeat: int
) -> tuple[bytes, bytes]:
    """Return independent structure and flag keys for one suite instance."""
    seed = _normalise_seed(master_seed)
    if not isinstance(domain, str) or not domain or len(domain.encode("utf-8")) > 128:
        raise ValueError("domain must be a non-empty UTF-8 string of at most 128 bytes")
    if task not in TASKS:
        raise ValueError(f"unknown task: {task}")
    if not isinstance(repeat, int) or isinstance(repeat, bool) or repeat < 1:
        raise ValueError("repeat must be a positive integer")
    domain_key = _derive(seed, "domain", domain)
    task_key = _derive(domain_key, "task", task)
    repeat_key = _derive(task_key, "repeat", str(repeat))
    return _derive(repeat_key, "structure"), _derive(repeat_key, "flag")


def _flag(flag_key: bytes) -> bytes:
    return f"BENCH{{{_derive(flag_key, 'value')[:16].hex()}}}".encode("ascii")


def _rng(structure_key: bytes) -> random.Random:
    return random.Random(int.from_bytes(structure_key, "big"))


def _input_hashes(folder: Path) -> dict[str, str]:
    return {
        path.relative_to(folder).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(folder.rglob("*"), key=lambda item: item.relative_to(folder).as_posix())
        if path.is_file()
    }


def _lcg_states(modulus: int, a: int, c: int, initial: int, count: int) -> list[int]:
    states = []
    state = initial
    for _ in range(count):
        state = (a * state + c) % modulus
        states.append(state)
    return states


def _lcg_candidates(document: dict) -> list[dict]:
    if "modulus" in document:
        raise ValueError("LCG modulus must not be published")
    observed = document.get("observations")
    if not isinstance(observed, list) or len(observed) != 18:
        raise ValueError("expected exactly eighteen noisy LCG observations")
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in observed):
        raise ValueError("LCG observations must be non-negative integers")

    # For four clean states, adjacent differences satisfy d[i+1] = a*d[i]
    # modulo m.  Therefore d[i+2]*d[i] - d[i+1]^2 is a multiple of m.
    # Two replaced readings only contaminate a bounded set of these windows,
    # so pairwise determinant GCDs expose the unknown 31-bit prime without
    # requiring general 64-bit factorisation.
    differences = [right - left for left, right in zip(observed, observed[1:])]
    determinants = [
        differences[index + 2] * differences[index]
        - differences[index + 1] * differences[index + 1]
        for index in range(len(differences) - 2)
    ]
    lower_bound = max(max(observed), 1 << 30)
    modulus_candidates: set[int] = set()
    nonzero = [abs(value) for value in determinants if value]
    for left, right in itertools.combinations(nonzero, 2):
        candidate = math.gcd(left, right)
        if lower_bound < candidate < (1 << 31) and _is_probable_prime(candidate):
            modulus_candidates.add(candidate)
    for value in nonzero:
        if lower_bound < value < (1 << 31) and _is_probable_prime(value):
            modulus_candidates.add(value)

    candidates: dict[tuple[int, int, int, tuple[int, ...]], dict] = {}
    for modulus in sorted(modulus_candidates):
        for index in range(len(observed) - 2):
            denominator = (observed[index + 1] - observed[index]) % modulus
            if denominator == 0:
                continue
            a = (
                (observed[index + 2] - observed[index + 1])
                * pow(denominator, -1, modulus)
            ) % modulus
            if a == 0:
                continue
            c = (observed[index + 1] - a * observed[index]) % modulus
            states = [0] * len(observed)
            states[index] = observed[index]
            inverse_a = pow(a, -1, modulus)
            for position in range(index - 1, -1, -1):
                states[position] = ((states[position + 1] - c) * inverse_a) % modulus
            for position in range(index + 1, len(states)):
                states[position] = (a * states[position - 1] + c) % modulus
            matches = sum(seen == expected for seen, expected in zip(observed, states))
            if matches != 16:
                continue
            faults = [
                position
                for position, (seen, expected) in enumerate(zip(observed, states))
                if seen != expected
            ]
            key = (modulus, a, c, tuple(states))
            candidates[key] = {
                "modulus": modulus,
                "a": a,
                "c": c,
                "states": states,
                "fault_positions": faults,
                "matching_observations": matches,
            }
    return list(candidates.values())


def _solve_lcg(document: dict) -> tuple[bytes, dict]:
    candidates = _lcg_candidates(document)
    valid = []
    ciphertext = bytes.fromhex(document["ciphertext"])
    for candidate in candidates:
        modulus = candidate["modulus"]
        state = candidate["states"][-1]
        plaintext = bytearray()
        for value in ciphertext:
            state = (candidate["a"] * state + candidate["c"]) % modulus
            plaintext.append(value ^ (state & 0xFF))
        if FLAG_RE.fullmatch(plaintext):
            valid.append((bytes(plaintext), candidate))
    if len(candidates) != 1 or len(valid) != 1:
        raise ValueError(f"LCG instance is not unique: {len(candidates)} parameter sets, {len(valid)} flags")
    plaintext, candidate = valid[0]
    return plaintext, {
        "candidate_count": len(candidates),
        "fault_positions": candidate["fault_positions"],
        "matching_observations": candidate["matching_observations"],
        "modulus": candidate["modulus"],
        "a": candidate["a"],
        "c": candidate["c"],
    }


def _make_lcg(rng: random.Random, flag: bytes) -> dict:
    for _ in range(256):
        modulus = _prime_31(rng)
        a = rng.randrange(2, modulus)
        c = rng.randrange(1, modulus)
        initial = rng.randrange(modulus)
        states = _lcg_states(modulus, a, c, initial, 18)
        observations = list(states)
        fault_positions = sorted(rng.sample(range(18), 2))
        for position in fault_positions:
            replacement = rng.randrange(modulus)
            while replacement == observations[position]:
                replacement = rng.randrange(modulus)
            observations[position] = replacement
        state = states[-1]
        ciphertext = bytearray()
        for value in flag:
            state = (a * state + c) % modulus
            ciphertext.append(value ^ (state & 0xFF))
        document = {
            "ciphertext": bytes(ciphertext).hex(),
            "observations": observations,
        }
        try:
            recovered, diagnostics = _solve_lcg(document)
        except ValueError:
            continue
        if recovered == flag and diagnostics["fault_positions"] == fault_positions:
            return document
    raise RuntimeError("could not construct a unique noisy LCG instance")


_SMALL_PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47)
_MR_BASES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)


def _is_probable_prime(value: int) -> bool:
    if value < 2:
        return False
    for prime in _SMALL_PRIMES:
        if value == prime:
            return True
        if value % prime == 0:
            return False
    odd = value - 1
    shifts = 0
    while odd % 2 == 0:
        shifts += 1
        odd //= 2
    for base in _MR_BASES:
        if base >= value:
            continue
        witness = pow(base, odd, value)
        if witness in (1, value - 1):
            continue
        for _ in range(shifts - 1):
            witness = pow(witness, 2, value)
            if witness == value - 1:
                break
        else:
            return False
    return True


def _prime_31(rng: random.Random) -> int:
    """Draw a deterministic 31-bit prime from the instance RNG."""
    for _ in range(100_000):
        candidate = rng.getrandbits(31) | (1 << 30) | 1
        if _is_probable_prime(candidate):
            return candidate
    raise RuntimeError("deterministic 31-bit prime search exhausted")


def _prime(rng: random.Random, bits: int, forbidden: set[int]) -> int:
    for _ in range(100_000):
        candidate = rng.getrandbits(bits) | (1 << (bits - 1)) | 1
        if candidate % 3 != 2 or candidate in forbidden:
            continue
        if _is_probable_prime(candidate):
            forbidden.add(candidate)
            return candidate
    raise RuntimeError("deterministic RSA prime search exhausted")


def _crt(residues: list[int], moduli: list[int]) -> int:
    product = math.prod(moduli)
    value = 0
    for residue, modulus in zip(residues, moduli):
        partial = product // modulus
        value += residue * partial * pow(partial, -1, modulus)
    return value % product


def _integer_cube_root(value: int) -> int:
    if value < 0:
        raise ValueError("cube root input must be non-negative")
    if value < 2:
        return value
    guess = 1 << ((value.bit_length() + 2) // 3)
    while True:
        next_guess = (2 * guess + value // (guess * guess)) // 3
        if next_guess >= guess:
            while (guess + 1) ** 3 <= value:
                guess += 1
            while guess**3 > value:
                guess -= 1
            return guess
        guess = next_guess


def _solve_rsa(document: dict) -> tuple[bytes, dict]:
    if document.get("e") != 3 or len(document.get("samples", [])) != 4:
        raise ValueError("expected four e=3 related-message samples")
    modulus = document.get("modulus")
    if not isinstance(modulus, int) or isinstance(modulus, bool) or modulus <= 0:
        raise ValueError("RSA modulus must be a positive integer")
    samples = document["samples"]
    offsets = [sample.get("offset") for sample in samples]
    if (
        any(not isinstance(offset, int) or isinstance(offset, bool) or offset <= 0 for offset in offsets)
        or len(set(offsets)) != 4
    ):
        raise ValueError("RSA offsets must be four distinct nonzero integers")

    # Subtract r^3 from c=(m+r)^3 to obtain
    #   y(r) = m^3 + 3*r*m^2 + 3*r^2*m (mod n).
    # Two first divided differences from any triple cancel m^3 and m^2,
    # leaving a linear equation for m.  Enumerating triples tolerates one
    # corrupted ciphertext while keeping every sample under a single modulus.
    candidates: dict[int, dict] = {}
    for indexes in itertools.combinations(range(4), 3):
        first, second, third = indexes
        r0, r1, r2 = (offsets[first], offsets[second], offsets[third])
        try:
            y0 = (samples[first]["ciphertext"] - pow(r0, 3, modulus)) % modulus
            y1 = (samples[second]["ciphertext"] - pow(r1, 3, modulus)) % modulus
            y2 = (samples[third]["ciphertext"] - pow(r2, 3, modulus)) % modulus
            d01 = (y1 - y0) * pow((r1 - r0) % modulus, -1, modulus) % modulus
            d02 = (y2 - y0) * pow((r2 - r0) % modulus, -1, modulus) % modulus
            message = (d01 - d02) * pow((3 * (r1 - r2)) % modulus, -1, modulus) % modulus
        except (KeyError, TypeError, ValueError):
            continue
        plaintext = message.to_bytes(max(1, (message.bit_length() + 7) // 8), "big")
        matching = [
            index
            for index, sample in enumerate(samples)
            if sample.get("ciphertext") == pow(message + offsets[index], 3, modulus)
        ]
        if len(matching) == 3 and FLAG_RE.fullmatch(plaintext):
            candidates[message] = {
                "matching_indexes": matching,
                "plaintext": plaintext,
            }
    if len(candidates) != 1:
        raise ValueError(f"RSA instance has {len(candidates)} valid related-message candidates")
    message, candidate = next(iter(candidates.items()))
    plaintext = candidate["plaintext"]
    matching = candidate["matching_indexes"]
    corrupt = [index for index in range(4) if index not in matching]
    if len(corrupt) != 1:
        raise ValueError("RSA instance does not contain exactly one corrupted ciphertext")
    return plaintext, {
        "candidate_count": len(candidates),
        "matching_indexes": matching,
        "corrupt_index": corrupt[0],
        "modulus": modulus,
    }


def _make_rsa(rng: random.Random, flag: bytes) -> dict:
    forbidden: set[int] = set()
    prime_left = _prime(rng, 176, forbidden)
    prime_right = _prime(rng, 176, forbidden)
    modulus = prime_left * prime_right
    message = int.from_bytes(flag, "big")
    offsets = rng.sample(range(1, 1 << 20), 4)
    if message + max(offsets) >= modulus:
        raise RuntimeError("RSA modulus is too small for the benchmark flag")
    correct = [pow(message + offset, 3, modulus) for offset in offsets]
    corrupt_index = rng.randrange(4)
    identifiers = [f"node-{value:02x}" for value in rng.sample(range(16, 240), 4)]
    for _ in range(256):
        ciphertexts = list(correct)
        delta = rng.randrange(1, modulus)
        ciphertexts[corrupt_index] = (ciphertexts[corrupt_index] + delta) % modulus
        samples = [
            {
                "ciphertext": ciphertexts[index],
                "id": identifiers[index],
                "offset": offsets[index],
            }
            for index in range(4)
        ]
        rng.shuffle(samples)
        if [sample["id"] for sample in samples] == identifiers:
            samples = samples[1:] + samples[:1]
        document = {"e": 3, "modulus": modulus, "samples": samples}
        try:
            recovered, _ = _solve_rsa(document)
        except ValueError:
            continue
        if recovered == flag:
            return document
    raise RuntimeError("could not construct a unique corrupted RSA related-message instance")


def _rol8(value: int, bits: int) -> int:
    return ((value << bits) | (value >> (8 - bits))) & 0xFF


def _ror8(value: int, bits: int) -> int:
    return ((value >> bits) | (value << (8 - bits))) & 0xFF


def _vm_apply(value: int, index: int, state: int, opcode: dict) -> int:
    name = opcode["op"]
    if name == "xor_key":
        return value ^ opcode["key"][index % len(opcode["key"])]
    if name == "add_const":
        return (value + opcode["value"]) & 0xFF
    if name == "xor_state":
        return value ^ state
    if name == "add_index":
        return (value + opcode["multiplier"] * index + opcode["offset"]) & 0xFF
    if name == "rotate_left":
        return _rol8(value, opcode["bits"])
    if name == "multiply_odd":
        return (value * opcode["value"]) & 0xFF
    raise ValueError(f"unknown VM opcode: {name}")


def _vm_reverse(value: int, index: int, state: int, opcode: dict) -> int:
    name = opcode["op"]
    if name == "xor_key":
        return value ^ opcode["key"][index % len(opcode["key"])]
    if name == "add_const":
        return (value - opcode["value"]) & 0xFF
    if name == "xor_state":
        return value ^ state
    if name == "add_index":
        return (value - opcode["multiplier"] * index - opcode["offset"]) & 0xFF
    if name == "rotate_left":
        return _ror8(value, opcode["bits"])
    if name == "multiply_odd":
        return (value * pow(opcode["value"], -1, 256)) & 0xFF
    raise ValueError(f"unknown VM opcode: {name}")


def _vm_next_state(state: int, plain: int, encoded: int, index: int, update: dict) -> int:
    mixed = _rol8(state ^ plain, update["rotate"])
    return (
        mixed * update["multiplier"]
        + encoded
        + index * update["index_multiplier"]
        + update["add"]
    ) & 0xFF


def _solve_vm(document: dict) -> tuple[bytes, dict]:
    if document.get("format") != "stateful-byte-vm-v3":
        raise ValueError("unexpected byte VM format")
    try:
        observed = bytes.fromhex(document["observed_low6"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("VM low-six-bit observations are malformed") from error
    if any(value > 0x3F for value in observed):
        raise ValueError("VM observations must contain only six-bit values")
    if document.get("input_length") != len(observed) or len(observed) != len(b"BENCH{" + b"0" * 32 + b"}"):
        raise ValueError("VM input length does not match the flag grammar")
    expected_ops = {
        "xor_key", "add_const", "xor_state", "add_index", "rotate_left", "multiply_odd"
    }
    opcodes = document.get("opcodes")
    if (
        not isinstance(opcodes, list)
        or len(opcodes) != len(expected_ops)
        or {opcode.get("op") for opcode in opcodes if isinstance(opcode, dict)} != expected_ops
    ):
        raise ValueError("VM must contain each of the six bijective opcodes exactly once")
    initial_state = document.get("initial_state")
    final_state = document.get("final_state")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 255
        for value in (initial_state, final_state)
    ):
        raise ValueError("VM states must be bytes")

    fixed = b"BENCH{"
    hexadecimal = b"0123456789abcdef"

    def allowed(index: int) -> bytes:
        if index < len(fixed):
            return bytes([fixed[index]])
        if index < len(fixed) + 32:
            return hexadecimal
        return b"}"

    # A frontier entry stores a capped path count and one witness.  Future
    # behaviour depends only on the byte-sized state, so merging equal states
    # is exact for uniqueness while bounding the frontier at 256 entries.
    frontier: dict[int, tuple[int, bytes]] = {initial_state: (1, b"")}
    frontier_sizes = [1]
    for index, low_six in enumerate(observed):
        next_frontier: dict[int, tuple[int, bytes]] = {}
        for state, (path_count, prefix) in frontier.items():
            for plain in allowed(index):
                encoded = plain
                for opcode in opcodes:
                    encoded = _vm_apply(encoded, index, state, opcode)
                if encoded & 0x3F != low_six:
                    continue
                next_state = _vm_next_state(
                    state, plain, encoded, index, document["state_update"]
                )
                previous_count, previous_witness = next_frontier.get(next_state, (0, b""))
                next_frontier[next_state] = (
                    min(2, previous_count + path_count),
                    previous_witness or prefix + bytes([plain]),
                )
        frontier = next_frontier
        frontier_sizes.append(len(frontier))
        if not frontier:
            break

    target = frontier.get(final_state)
    solution_count = 0 if target is None else target[0]
    if solution_count != 1:
        raise ValueError(f"VM grammar has {solution_count} solutions (2 means multiple)")
    plaintext = target[1]
    if not FLAG_RE.fullmatch(plaintext):
        raise ValueError("VM grammar solution is not a benchmark flag")

    state = initial_state
    locally_ambiguous = []
    for index, plain in enumerate(plaintext):
        matching = []
        full_encoded = None
        for candidate_plain in allowed(index):
            candidate_encoded = candidate_plain
            for opcode in opcodes:
                candidate_encoded = _vm_apply(candidate_encoded, index, state, opcode)
            if candidate_encoded & 0x3F == observed[index]:
                matching.append(candidate_plain)
            if candidate_plain == plain:
                full_encoded = candidate_encoded
        if len(matching) >= 2:
            locally_ambiguous.append(index)
        if full_encoded is None:
            raise ValueError("VM witness failed replay")
        state = _vm_next_state(
            state, plain, full_encoded, index, document["state_update"]
        )
    if state != final_state:
        raise ValueError("VM witness does not reach the published final state")
    return plaintext, {
        "opcode_order": [opcode["op"] for opcode in document["opcodes"]],
        "final_state": state,
        "solution_count": solution_count,
        "max_frontier_states": max(frontier_sizes),
        "locally_ambiguous_positions": locally_ambiguous,
    }


def _make_vm(rng: random.Random, flag: bytes) -> dict:
    odd_values = list(range(3, 256, 2))
    for _ in range(4096):
        opcodes = [
            {"op": "xor_key", "key": [rng.randrange(256) for _ in range(rng.randrange(5, 10))]},
            {"op": "add_const", "value": rng.randrange(1, 256)},
            {"op": "xor_state"},
            {"op": "add_index", "multiplier": rng.randrange(1, 256), "offset": rng.randrange(256)},
            {"op": "rotate_left", "bits": rng.randrange(1, 8)},
            {"op": "multiply_odd", "value": rng.choice(odd_values)},
        ]
        rng.shuffle(opcodes)
        update = {
            "add": rng.randrange(256),
            "index_multiplier": rng.randrange(1, 256),
            "multiplier": rng.choice(odd_values),
            "rotate": rng.randrange(1, 8),
        }
        initial_state = rng.randrange(256)
        state = initial_state
        observations = bytearray()
        for index, plain in enumerate(flag):
            encoded = plain
            for opcode in opcodes:
                encoded = _vm_apply(encoded, index, state, opcode)
            observations.append(encoded & 0x3F)
            state = _vm_next_state(state, plain, encoded, index, update)
        document = {
            "final_state": state,
            "format": "stateful-byte-vm-v3",
            "initial_state": initial_state,
            "input_length": len(flag),
            "observed_low6": bytes(observations).hex(),
            "opcodes": opcodes,
            "state_update": update,
        }
        try:
            recovered, diagnostics = _solve_vm(document)
        except ValueError:
            continue
        if recovered == flag and len(diagnostics["locally_ambiguous_positions"]) >= 4:
            return document
    raise RuntimeError("could not construct a unique partially observed byte VM")


def _crc32(value: bytes) -> int:
    return zlib.crc32(value) & 0xFFFFFFFF


def _xor_padded(parts: list[bytes], width: int) -> bytes:
    parity = bytearray(width)
    for part in parts:
        for index, value in enumerate(part):
            parity[index] ^= value
    return bytes(parity)


def _gf256_mul(left: int, right: int) -> int:
    """Multiply bytes in GF(2^8) using the AES polynomial x^8+x^4+x^3+x+1."""
    if not 0 <= left <= 0xFF or not 0 <= right <= 0xFF:
        raise ValueError("GF(256) operands must be bytes")
    result = 0
    value = left
    multiplier = right
    for _ in range(8):
        if multiplier & 1:
            result ^= value
        high = value & 0x80
        value = (value << 1) & 0xFF
        if high:
            value ^= 0x1B
        multiplier >>= 1
    return result


def _gf256_inverse(value: int) -> int:
    if not 1 <= value <= 0xFF:
        raise ValueError("only nonzero GF(256) elements are invertible")
    result = 1
    base = value
    exponent = 254
    while exponent:
        if exponent & 1:
            result = _gf256_mul(result, base)
        base = _gf256_mul(base, base)
        exponent >>= 1
    return result


def _gf256_parity(parts: list[bytes], coefficients: list[int], width: int) -> bytes:
    if len(parts) != len(coefficients):
        raise ValueError("one GF(256) coefficient is required per fragment")
    parity = bytearray(width)
    for part, coefficient in zip(parts, coefficients):
        for index, value in enumerate(part):
            parity[index] ^= _gf256_mul(coefficient, value)
    return bytes(parity)


def _solve_fragment(rows: list[dict]) -> tuple[bytes, dict]:
    starts = [row for row in rows if row.get("event") == "start" and row.get("codec") == "zlib"]
    if len(starts) != 1:
        raise ValueError("capture must contain exactly one zlib transfer start")
    metadata = starts[0]
    transfer = metadata["transfer"]
    target_rows = [row for row in rows if row.get("transfer") == transfer]
    data_rows = [row for row in target_rows if row.get("event") == "data"]
    invalid = []
    valid_by_sequence: dict[int, list[bytes]] = {}
    for row in data_rows:
        value = base64.b64decode(row["data"], validate=True)
        if _crc32(value) != row["crc32"]:
            invalid.append(row)
        else:
            valid_by_sequence.setdefault(row["seq"], []).append(value)
    if len(invalid) != 1:
        raise ValueError("capture must contain exactly one bad-CRC target record")
    duplicates = [sequence for sequence, values in valid_by_sequence.items() if len(values) != 1]
    if duplicates:
        raise ValueError("valid target fragments must be unique by sequence")
    chunks = metadata.get("chunks")
    chunk_size = metadata.get("chunk_size")
    compressed_length = metadata.get("compressed_length")
    coefficients = metadata.get("coefficients")
    if (
        not isinstance(chunks, int)
        or isinstance(chunks, bool)
        or chunks < 3
        or not isinstance(chunk_size, int)
        or isinstance(chunk_size, bool)
        or chunk_size <= 0
        or not isinstance(compressed_length, int)
        or isinstance(compressed_length, bool)
        or not (chunk_size * (chunks - 1) < compressed_length <= chunk_size * chunks)
    ):
        raise ValueError("fragment metadata dimensions are invalid")
    if (
        metadata.get("gf256_polynomial") != 0x11B
        or not isinstance(coefficients, list)
        or len(coefficients) != chunks
        or any(
            not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 255
            for value in coefficients
        )
        or len(set(coefficients)) != chunks
    ):
        raise ValueError("fragment GF(256) coefficients must be distinct nonzero bytes")
    for sequence, values in valid_by_sequence.items():
        if not isinstance(sequence, int) or isinstance(sequence, bool) or not 0 <= sequence < chunks:
            raise ValueError("fragment sequence is outside the transfer")
        expected_length = (
            chunk_size if sequence < chunks - 1 else compressed_length - chunk_size * (chunks - 1)
        )
        if len(values[0]) != expected_length:
            raise ValueError("fragment length does not match its sequence")
    missing = [sequence for sequence in range(chunks) if sequence not in valid_by_sequence]
    if len(missing) != 2:
        raise ValueError("capture must omit exactly two target fragments")
    parity_rows = [row for row in target_rows if row.get("event") == "parity"]
    if len(parity_rows) != 2 or {row.get("kind") for row in parity_rows} != {"xor", "gf256"}:
        raise ValueError("capture must contain one XOR and one GF(256) parity record")
    parity_values = {}
    for row in parity_rows:
        try:
            parity = base64.b64decode(row["data"], validate=True)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("parity record is malformed") from error
        if _crc32(parity) != row.get("crc32") or len(parity) != chunk_size:
            raise ValueError("parity record failed validation")
        parity_values[row["kind"]] = parity

    xor_residual = bytearray(parity_values["xor"])
    gf_residual = bytearray(parity_values["gf256"])
    for sequence, values in valid_by_sequence.items():
        for index, value in enumerate(values[0]):
            xor_residual[index] ^= value
            gf_residual[index] ^= _gf256_mul(coefficients[sequence], value)
    left_sequence, right_sequence = missing
    left_coefficient = coefficients[left_sequence]
    right_coefficient = coefficients[right_sequence]
    inverse_difference = _gf256_inverse(left_coefficient ^ right_coefficient)
    left_part = bytearray(chunk_size)
    right_part = bytearray(chunk_size)
    for index, xor_value in enumerate(xor_residual):
        left_value = _gf256_mul(
            inverse_difference,
            gf_residual[index] ^ _gf256_mul(right_coefficient, xor_value),
        )
        left_part[index] = left_value
        right_part[index] = xor_value ^ left_value
    for sequence, recovered in ((left_sequence, left_part), (right_sequence, right_part)):
        expected_length = (
            chunk_size if sequence < chunks - 1 else compressed_length - chunk_size * (chunks - 1)
        )
        if any(recovered[expected_length:]):
            raise ValueError("recovered final fragment has nonzero padding")
        valid_by_sequence[sequence] = [bytes(recovered[:expected_length])]

    compressed = b"".join(valid_by_sequence[index][0] for index in range(chunks))
    if hashlib.sha256(compressed).hexdigest() != metadata["payload_sha256"]:
        raise ValueError("recovered compressed payload hash mismatch")
    plaintext = zlib.decompress(compressed)
    if not FLAG_RE.fullmatch(plaintext):
        raise ValueError("fragment transfer did not decode to a benchmark flag")
    bad_sequence = invalid[0]["seq"]
    matching_good = [
        row for row in data_rows
        if row["seq"] == bad_sequence and _crc32(base64.b64decode(row["data"])) == row["crc32"]
    ]
    if len(matching_good) != 1 or rows.index(invalid[0]) >= rows.index(matching_good[0]):
        raise ValueError("bad target record must have one later valid retransmission")
    return plaintext, {
        "bad_crc_count": 1,
        "bad_sequence": bad_sequence,
        "missing_sequences": missing,
        "parity_kinds": sorted(parity_values),
        "payload_sha256": metadata["payload_sha256"],
    }


def _make_fragment(rng: random.Random, flag: bytes) -> list[dict]:
    compressed = zlib.compress(flag, level=9)
    chunk_size = rng.randrange(7, 12)
    parts = [compressed[index : index + chunk_size] for index in range(0, len(compressed), chunk_size)]
    missing = sorted(rng.sample(range(len(parts)), 2))
    retransmit = rng.choice([index for index in range(len(parts)) if index not in missing])
    coefficients = rng.sample(range(1, 256), len(parts))
    transfer = rng.randbytes(8).hex()
    start = {
        "chunk_size": chunk_size,
        "chunks": len(parts),
        "codec": "zlib",
        "coefficients": coefficients,
        "compressed_length": len(compressed),
        "event": "start",
        "gf256_polynomial": 0x11B,
        "parity": ["xor", "gf256"],
        "payload_sha256": hashlib.sha256(compressed).hexdigest(),
        "transfer": transfer,
    }
    middle = []
    bad_row = None
    good_row = None
    for sequence, part in enumerate(parts):
        if sequence in missing:
            continue
        row = {
            "crc32": _crc32(part),
            "data": base64.b64encode(part).decode("ascii"),
            "event": "data",
            "seq": sequence,
            "transfer": transfer,
        }
        middle.append(row)
        if sequence == retransmit:
            good_row = row
            damaged = bytearray(part)
            damaged[rng.randrange(len(damaged))] ^= rng.randrange(1, 256)
            bad_row = {
                "crc32": _crc32(part),
                "data": base64.b64encode(damaged).decode("ascii"),
                "event": "data",
                "seq": sequence,
                "transfer": transfer,
            }
            middle.append(bad_row)
    parity_values = {
        "xor": _xor_padded(parts, chunk_size),
        "gf256": _gf256_parity(parts, coefficients, chunk_size),
    }
    for kind, parity in parity_values.items():
        middle.append({
            "crc32": _crc32(parity),
            "data": base64.b64encode(parity).decode("ascii"),
            "event": "parity",
            "kind": kind,
            "transfer": transfer,
        })
    used_transfers = {transfer}
    for _ in range(16):
        decoy_transfer = rng.randbytes(8).hex()
        while decoy_transfer in used_transfers:
            decoy_transfer = rng.randbytes(8).hex()
        used_transfers.add(decoy_transfer)
        value = rng.randbytes(rng.randrange(3, 12))
        middle.append({
            "crc32": _crc32(value),
            "data": base64.b64encode(value).decode("ascii"),
            "event": "data",
            "seq": rng.randrange(12),
            "transfer": decoy_transfer,
        })
    rng.shuffle(middle)
    assert bad_row is not None and good_row is not None
    if middle.index(bad_row) > middle.index(good_row):
        left, right = middle.index(bad_row), middle.index(good_row)
        middle[left], middle[right] = middle[right], middle[left]
    complete = {"event": "complete", "status": "received", "transfer": transfer}
    return [start, *middle, complete]


def reference_decode_instance(task: str, folder: Path) -> tuple[bytes, dict]:
    """Reference-decode a generated hard instance for generation/tests only."""
    folder = Path(folder)
    if task == "lcg_stream":
        return _solve_lcg(json.loads((folder / "stream.json").read_text(encoding="utf-8")))
    if task == "shared_rsa":
        return _solve_rsa(json.loads((folder / "public.json").read_text(encoding="utf-8")))
    if task == "byte_machine":
        return _solve_vm(json.loads((folder / "program.json").read_text(encoding="utf-8")))
    if task == "fragment_log":
        rows = [json.loads(line) for line in (folder / "capture.jsonl").read_text(encoding="utf-8").splitlines()]
        return _solve_fragment(rows)
    raise ValueError(f"{task!r} is not a hard task with a reference decoder")


def _write_instance(folder: Path, task: str, rng: random.Random, flag: bytes) -> None:
    _, description = TASKS[task]
    _write_text(folder / "challenge.txt", description + "\nFlag: BENCH{32 lowercase hex digits}\n")
    if task == "layered":
        payload = base64.b85encode(zlib.compress(flag[::-1], level=9))
        (folder / "message.bin").write_bytes(gzip.compress(payload, mtime=0))
        _write_text(folder / "sender.txt", "Sender pipeline: reverse bytes, deflate, Base85, gzip.\n")
    elif task == "repeating_xor":
        key = rng.randbytes(5)
        while key == b"\0" * 5:
            key = rng.randbytes(5)
        (folder / "cipher.bin").write_bytes(bytes(value ^ key[index % 5] for index, value in enumerate(flag)))
        _write_text(folder / "format.txt", "The key is exactly five bytes. No salt or IV.\n")
    elif task == "lcg_stream":
        write_json(folder / "stream.json", _make_lcg(rng, flag))
        _write_text(
            folder / "lcg-spec.txt",
            "Eighteen post-step LCG states were recorded in order; exactly two readings were replaced.\n"
            "state = (a * state + c) mod p, with unknown 31-bit prime p and 0 < a < p.\n"
            "After the eighteenth true state, step once per plaintext byte and XOR with state & 255.\n",
        )
    elif task == "shared_rsa":
        write_json(folder / "public.json", _make_rsa(rng, flag))
        _write_text(
            folder / "broadcast.txt",
            "Four known, distinct, nonzero offsets r_i share one textbook RSA modulus n and exponent 3.\n"
            "Each record is c_i = (m + r_i)^3 mod n; records were reordered and exactly one ciphertext was corrupted.\n",
        )
    elif task == "byte_machine":
        write_json(folder / "program.json", _make_vm(rng, flag))
        _write_text(
            folder / "vm-spec.txt",
            "All byte arithmetic is modulo 256. Apply opcodes in listed order for each input byte.\n"
            "xor_key: XOR key[i % len(key)]; add_const: add value; xor_state: XOR current state.\n"
            "add_index: add multiplier*i+offset; rotate_left: rotate by bits; multiply_odd: multiply by value.\n"
            "After producing the full byte y, update state = (ROL8(state XOR input, rotate) * multiplier\n"
            "  + y + i * index_multiplier + add) mod 256 using state_update.\n"
            "Only y & 0x3f is observed. Recover the grammar-constrained flag that also reaches final_state.\n",
        )
    elif task == "fragment_log":
        rows = _make_fragment(rng, flag)
        _write_text(folder / "capture.jsonl", "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows))
        _write_text(
            folder / "protocol.txt",
            "The zlib transfer has exactly two absent data sequences and one bad-CRC record followed by a valid retransmission.\n"
            "The XOR parity is P; the GF(256) parity is Q = XOR(coefficients[seq] * chunk).\n"
            "GF(256) multiplication uses polynomial 0x11b, and chunks are padded with zeroes to chunk_size.\n"
            "Trim recovery to compressed_length and verify payload_sha256 before decompression.\n",
        )
    else:
        raise ValueError(f"unknown task: {task}")


def generate(
    root: Path,
    repeats: int,
    master_seed: bytes | bytearray | str,
    domain: str = "main",
    tasks: list[str] | tuple[str, ...] | None = None,
) -> dict:
    """Generate a byte-stable suite from an explicit seed and derivation domain."""
    seed = _normalise_seed(master_seed)
    if not 1 <= repeats <= 20:
        raise ValueError("repeats must be between 1 and 20")
    selected = list(TASKS) if tasks is None else list(tasks)
    if not selected or len(selected) != len(set(selected)) or any(task not in TASKS for task in selected):
        raise ValueError("tasks must be a non-empty unique subset of TASKS")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    answer_key = {}
    for repeat in range(1, repeats + 1):
        for task in selected:
            category, _ = TASKS[task]
            task_id = f"{task}-r{repeat}"
            folder = root / task_id / "untrusted"
            folder.mkdir(parents=True)
            structure_key, flag_key = derive_instance_material(seed, domain, task, repeat)
            flag = _flag(flag_key)
            _write_instance(folder, task, _rng(structure_key), flag)
            if task in HARD_TASKS:
                recovered, _ = reference_decode_instance(task, folder)
                if recovered != flag:
                    raise RuntimeError(f"reference decoder mismatch for {task_id}")
            answer_key[task_id] = {
                "category": category,
                "flag_sha256": hashlib.sha256(flag).hexdigest(),
                "hashes": _input_hashes(folder),
                "repeat": repeat,
                "task": task,
            }
    write_json(root / "answer-key.json", answer_key)
    return answer_key


def _seed_from_file(path: Path) -> bytes:
    value = path.read_bytes()
    if len(value) == 32:
        return value
    try:
        text = value.decode("ascii").strip()
    except UnicodeDecodeError as error:
        raise ValueError("master seed file must contain 32 raw bytes or 64 hex characters") from error
    return _normalise_seed(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--domain", default="main")
    parser.add_argument("--tasks", nargs="+", choices=tuple(TASKS))
    seeds = parser.add_mutually_exclusive_group(required=True)
    seeds.add_argument("--master-seed-hex", help="exactly 64 hex characters; never echoed")
    seeds.add_argument("--master-seed-file", type=Path, help="file containing 32 raw bytes or 64 hex characters")
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20:
        parser.error("repeats must be between 1 and 20")
    try:
        seed = _seed_from_file(args.master_seed_file) if args.master_seed_file else _normalise_seed(args.master_seed_hex)
        manifest = generate(args.destination, args.repeats, seed, args.domain, args.tasks)
    except (TypeError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"destination": str(args.destination), "instances": len(manifest), "suite_version": SUITE_VERSION}))


if __name__ == "__main__":
    main()
