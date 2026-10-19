#!/usr/bin/env python3
"""Check portable agent assets; --sync updates only an unchanged managed mirror.

Requires Python 3.11+. No network, package installation, challenge execution, or
event-data inspection. .claude/skills is canonical; .agents/skills is generated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib

SKILLS = {
    "ctf-ai-ml", "ctf-crypto", "ctf-forensics", "ctf-malware", "ctf-misc",
    "ctf-osint", "ctf-pwn", "ctf-reverse", "ctf-web", "ctf-writeup",
    "solve-challenge",
}
ROLES = ("solver", "triager", "verifier")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(root: Path, path: Path) -> None:
    """Reject escapes and symlink/junction parents before any managed write."""
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes workspace: {path}")
    current = path
    while current != root:
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError(f"Managed paths must not be links: {current}")
        if current.exists() and getattr(current.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400:
            raise ValueError(f"Managed paths must not be reparse points: {current}")
        current = current.parent


def files_at(root: Path, directory: Path) -> dict[str, Path]:
    safe_path(root, directory)
    if not directory.is_dir():
        return {}
    result = {}
    for path in sorted(directory.rglob("*")):
        safe_path(root, path)
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = path
    return result


def local_links(path: Path):
    """Yield file links outside code fences; fragments are checked as file paths."""
    fence = None
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            if fence is None:
                fence = marker.group(1)[0]
            elif marker.group(1)[0] == fence:
                fence = None
            continue
        if fence:
            continue
        line = re.sub(r"(`+).*?\1", "", line)
        for match in re.finditer(r"\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)", line):
            target = match.group(1).split("#", 1)[0]
            if target and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                yield line_no, target


def run(root: Path, sync: bool) -> list[str]:
    errors = []
    source_dir, mirror_dir = root / ".claude/skills", root / ".agents/skills"
    source, mirror = files_at(root, source_dir), files_at(root, mirror_dir)
    actual_skills = {name.split("/")[0] for name in source if name.endswith("/SKILL.md")}
    if actual_skills != SKILLS:
        errors.append(f"Expected 11 skills; missing={sorted(SKILLS-actual_skills)}, extra={sorted(actual_skills-SKILLS)}")
    manifest_path = root / "tools/workspace-manifest.json"
    safe_path(root, manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    known = manifest.get("skill_sha256", {})
    hashes = {rel: digest(path) for rel, path in source.items()}
    extra = sorted(mirror.keys() - source.keys())
    if extra:
        errors.append(f"Unmanaged mirror files (preserved): {extra}")
    for rel, path in mirror.items():
        if rel in hashes and digest(path) not in (hashes[rel], known.get(rel)):
            errors.append(f"Local mirror edit preserved: .agents/skills/{rel}; reconcile into .claude/skills first")
    for rel, path in source.items():
        if path.name == "SKILL.md":
            body = path.read_text(encoding="utf-8-sig")
            if not body.startswith("---\n") or not re.search(r"^name:\s*" + re.escape(path.parent.name) + r"\s*$", body, re.M):
                errors.append(f"Invalid skill identity: {path.relative_to(root)}")
            if not re.search(r"^description:\s*\S", body, re.M):
                errors.append(f"Missing skill description: {path.relative_to(root)}")
        if path.suffix == ".md":
            for line_no, target in local_links(path):
                if not (path.parent / target).exists():
                    errors.append(f"Broken link: {path.relative_to(root)}:{line_no} -> {target}")
    for role in ROLES:
        path = root / f".codex/agents/{role}.toml"
        if not path.is_file():
            errors.append(f"Missing Codex role: {path.relative_to(root)}")
            continue
        data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
        if data.get("name") != role or not data.get("description") or not data.get("developer_instructions"):
            errors.append(f"Invalid Codex role: {path.relative_to(root)}")
        if not (root / f".claude/agents/{role}.md").is_file():
            errors.append(f"Missing Claude role: {role}")
    pin = root / "tools/vendor-ctf-skills/PINNED_COMMIT.txt"
    if not pin.is_file() or not re.fullmatch(r"[0-9a-f]{40}", pin.read_text().strip()):
        errors.append("Missing/invalid upstream commit pin")
    if not (root / "tools/vendor-ctf-skills/LICENSE").is_file():
        errors.append("Missing upstream license notice")
    for required in ("CLAUDE.md", "AGENTS.md", "docs/SKILL-INTEGRATION.md", "docs/PRE-CTF-INTAKE.md", "events/_TEMPLATE/NOTES.md"):
        if not (root / required).is_file():
            errors.append(f"Missing required asset: {required}")
    if sync and not errors:
        for rel, path in source.items():
            dest = mirror_dir / rel
            safe_path(root, dest)
            if not dest.exists() or digest(dest) != hashes[rel]:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(path.read_bytes())
        manifest_path.write_text(json.dumps({
            "schema_version": 1,
            "canonical": ".claude/skills",
            "mirror": ".agents/skills",
            "upstream_commit": pin.read_text().strip(),
            "skill_sha256": hashes,
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    elif not sync:
        if hashes != known:
            errors.append("Canonical hashes differ from manifest; review changes, then run --sync")
        for rel, expected in hashes.items():
            if rel not in mirror or digest(mirror[rel]) != expected:
                errors.append(f"Mirror missing/outdated: .agents/skills/{rel}")
    if not errors:
        markdown = sum(path.suffix == ".md" for path in source.values())
        print(f"PASS: {len(SKILLS)} skills, {len(source)} files ({markdown} Markdown), 3 Codex roles; mirror {'synced' if sync else 'matches'}")
        print("Scope: static asset checks only; no model, sandbox, or fresh-machine install validation.")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync", action="store_true", help="update unchanged mirror and canonical hash manifest")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="workspace root (for export/fixture validation)")
    args = parser.parse_args()
    try:
        errors = run(args.root.resolve(), args.sync)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors = [str(error)]
    for error in errors:
        print(f"FAIL: {error}", file=sys.stderr)
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
