#!/usr/bin/env python3
"""Export reviewed working files for a separate student Git repository.

Python 3.11+, standard library only. Never copies the source Git history,
initializes Git, commits, pushes, downloads, or executes challenge files.
The destination must be an empty directory inside this workspace's dist/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

SCHEMA_VERSION = 1
EXACT_FILES = (
    ".gitattributes", ".gitignore", "README.md", "AGENTS.md", "CLAUDE.md", "setup.ps1",
    "events/README.md", "events/_TEMPLATE/NOTES.md",
    "docs/BOOTSTRAP.md", "docs/PRE-CTF-INTAKE.md", "docs/STUDENT-GUIDE.md",
    "docs/TROUBLESHOOTING.md", "docs/SKILL-INTEGRATION.md",
    "docs/INTEGRATIONS.md",
    "tools/check-workspace.py", "tools/workspace-manifest.json",
    "tools/new-challenge.sh", "tools/codex-crosscheck.sh",
    "tools/setup-integrations.ps1", "tools/repair-wsl-service.ps1",
    "tools/rea.sh",
    "tools/integrations/setup.py", "tools/integrations/reviewed-versions.json",
    "tools/integrations/install-rea.sh",
    "tools/wsl/setup-ubuntu-ctf.ps1", "tools/wsl/provision-ubuntu-ctf.sh",
    "tools/wsl/ctf-venv-requirements.txt",
    "tools/vendor-ctf-skills/PINNED_COMMIT.txt", "tools/vendor-ctf-skills/LICENSE",
    "tools/vendor-ctf-skills/scripts/install_ctf_tools.sh",
)
TREE_FILES = (".claude/agents", ".claude/skills", ".agents/skills", ".codex/agents")
TEXT_EXTENSIONS = {".md", ".py", ".sh", ".ps1", ".txt", ".json", ".toml"}
EXTENSIONLESS = {".gitattributes", ".gitignore", "LICENSE"}
MANIFEST_NAME = "STUDENT-EXPORT-MANIFEST.json"
SECRET_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})\b")),
    ("provider API key", re.compile(r"\bsk-(?:proj-|ant-api\d{2}-)?[A-Za-z0-9_-]{32,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{30,}\b")),
)

STUDENT_README = """# CTF Workspace — 학생 저장소

Claude Code와 Codex로 CTF를 분석할 때 사용하는 운영 규칙, 스킬, 역할,
설치 도구와 실습 안내입니다. 문제마다 정찰, 가설 하나, 최소 검증, 증거 기록,
독립 재실행을 수행하며 플래그는 사람이 제출합니다.

강사가 공지한 학생용 저장소 URL과 전체 커밋 ID로 받습니다.
[학생 안내](docs/STUDENT-GUIDE.md)의 clone/fetch 및 커밋 확인 절차를 먼저 따르고,
[설치 안내](docs/BOOTSTRAP.md)로 실행 환경을 준비합니다.

- `CLAUDE.md` / `AGENTS.md`: 두 도구의 공통 운영 규칙.
- `.claude/skills/` / `.agents/skills/`: 11개 CTF 스킬 원본과 Codex 미러.
- `.claude/agents/` / `.codex/agents/`: triager, solver, verifier 역할.
- `tools/`: 정적 검사, 챌린지 골격, Codex 교차검증과 WSL 설치 도구.
- `docs/`: 학생 실습, 설치, 인테이크, 트러블슈팅, 스킬 적용 안내.
- `events/_TEMPLATE/`: 이벤트 기록 템플릿. 실제 이벤트 자료는 로컬에 둡니다.

Python 3.11+에서 `python -I tools/check-workspace.py`로 자산을 확인합니다.
Windows에서는 `powershell -File setup.ps1`로 관리 미러를 동기화합니다.
스킬은 `.claude/skills/`에서 수정한 뒤 검토하고 다시 동기화합니다.
신뢰할 수 없는 파일의 분석과 실행은 준비한 전용 Linux 환경에서 수행합니다.

REA/Ghidra의 설치·진단은 [통합 안내](docs/INTEGRATIONS.md)를 따릅니다.
별도 runtime은 학생 Git에 포함하지 않으며 각 단말에서 설치합니다.

모델 CLI 로그인, OS 이미지, 이벤트 문제와 계정은 각 환경에서 별도로 준비합니다.
이 저장소에는 강사용 PPT, 벤치마크 실행 원본, 실제 이벤트, 자격증명이 없습니다.
스킬·규칙과 WSL은 완전한 보안 경계가 아니므로 실행 권한과 환경을 확인합니다.

`STUDENT-EXPORT-MANIFEST.json`은 배포 파일의 원본 및 출력 SHA-256과 적용한
문서 변환을 기록합니다. 원본 개발 저장소의 Git 이력은 포함하지 않습니다.
벤더 자료의 MIT 고지는 `tools/vendor-ctf-skills/LICENSE`에 있습니다.
"""

STUDENT_IGNORE = """# Event inputs, solve work, notes and flags stay local.
events/*
!events/README.md
!events/_TEMPLATE/
!events/_TEMPLATE/**
__pycache__/
*.pyc
.venv/
.venv-tools/
node_modules/
dist/
.integrations/
.mcp.json
.mcp.json.pre-integrations.backup
.mcp.json.integration-tmp
.codex/config.toml
.codex/config.toml.pre-integrations.backup
.codex/config.toml.integration-tmp
.claude/settings.local.json
.claude/settings.json
.codex/auth.json
.env
.env.*
*.pem
*.key
~$*
# Instructor assets and benchmark raw data do not enter this repository.
*.ppt
*.pptx
*.pot
*.potx
*.pdf
*.zip
benchmarks/
docs/*-deck-build/
tools/build-*deck*
"""

STUDENT_ENVIRONMENT = """## 환경
- Windows에서는 전용 WSL 배포판 `ubuntu-ctf`를 `docs/BOOTSTRAP.md`에 따라
  준비한다. 신뢰할 수 없는 바이너리/파일 분석은 반드시 전용 Linux 안에서
  실행하고 호스트에서는 실행하지 않는다. `wsl -d ubuntu-ctf`로 진입한다.
  설치 후 CTF venv `~/.ctf-tools/venv`, 필요한 도구와 Docker 상태를 확인한다.
  저장소 경로는 자신의 clone 위치를 사용한다. 예를 들어 Windows의
  `C:\\CTF-Class\\ctf-workspace`는 WSL의 `/mnt/c/CTF-Class/ctf-workspace`이다.
  챌린지가 컨테이너를 제공하면 준비한 Linux에서 이를 사용한다.
- 원본 챌린지 파일은 `<challenge>/untrusted/`에 보관한다. 모든 작업은
  `<challenge>/work/`에서 한다. 경로는 인자로 넘기고, untrusted 디렉터리
  안에서는 절대 인터프리터를 실행하지 않는다. 분석용 Python은 `python -I`로 실행한다.
- Windows+WSL+Bash 도구 관련 함정과 해결책은 `docs/TROUBLESHOOTING.md`에 있다.
  셸과 씨름하기 전에 먼저 읽는다. 지속 작업은 tmux 세션
  (`tmux new-session -d -s ctf`)에서 돌린다. 사용자는
  `wsl -d ubuntu-ctf -- tmux attach -t ctf`로 접속할 수 있다.

"""

STUDENT_BENCHMARK = """## 10. 벤치마크 수업

같은 문제 입력과 도구 환경, 같은 시간 제한에서 Claude 단독, Codex 단독,
프로젝트 하네스의 최종 결과를 비교합니다. 하네스는 규칙·스킬·기록 템플릿을
적용하여 Claude 풀이 → Codex 검토 → Claude 수정의 흐름을 사용합니다.

최종 정답, 같은 입력 및 새 입력 재실행, 전체 시간과 단계별 사용량을 기록합니다.
실패·타임아웃·인프라 오류도 분모와 함께 남깁니다. 가설의 선행 기록, 재현 명령,
원시 관측과 판단의 연결, writeup 전달성을 각각 0~2점으로 평가합니다.
확인하지 못한 준수 항목과 미평가 결과는 따로 표시합니다.

강사가 공개 검토를 마친 결과를 제공하기 전에는 향상률을 주장하지 않습니다.
하네스에는 규칙·스킬과 두 번째 모델 검토가 함께 적용되므로 어느 요소 하나의
인과 효과로 해석하지 않습니다. 합성 문제 결과는 실제 대회 전체를 대표하지 않습니다.
실행 원본, 정답 seed와 평가 기록은 학생 저장소에 포함하지 않습니다.

"""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_no_links(path: Path) -> None:
    """Inspect even dangling links and Windows reparse points in every ancestor."""
    current = path.absolute()
    while True:
        try:
            info = current.lstat()
        except FileNotFoundError:
            pass
        else:
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError(f"Symlink, junction or reparse point is forbidden: {current}")
        if current.parent == current:
            break
        current = current.parent


def checked_relative(root: Path, relative: str) -> Path:
    rel = PurePosixPath(relative)
    if rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts) or "\\" in relative or ":" in relative:
        raise ValueError(f"Invalid relative path: {relative}")
    path = root.joinpath(*rel.parts)
    check_no_links(path)
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"Path escapes source root: {relative}")
    return path


def allowed_type(relative: str) -> None:
    path = PurePosixPath(relative)
    if path.suffix.lower() not in TEXT_EXTENSIONS and path.name not in EXTENSIONLESS:
        raise ValueError(f"Unallowed file type in allowlist: {relative}")


def selected_files(root: Path) -> list[str]:
    paths = set(EXACT_FILES)
    for directory in TREE_FILES:
        path = checked_relative(root, directory)
        if not path.is_dir():
            raise ValueError(f"Missing required directory: {directory}")
        for parent, directories, files in os.walk(path, followlinks=False):
            for name in sorted(directories + files):
                item = Path(parent) / name
                check_no_links(item)
                if item.is_file():
                    paths.add(item.relative_to(root).as_posix())
                elif not item.is_dir():
                    raise ValueError(f"Nonregular selected asset: {item}")
    for relative in sorted(paths):
        path = checked_relative(root, relative)
        if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
            raise ValueError(f"Missing or nonregular required asset: {relative}")
        allowed_type(relative)
    return sorted(paths)


def normalize(relative: str, text: str) -> tuple[str, list[str]]:
    changes = []
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if relative == "README.md":
        return STUDENT_README, ["student-readme"]
    if relative == ".gitignore":
        return STUDENT_IGNORE, ["student-ignore"]
    if relative == ".gitattributes":
        lines = [line for line in text.splitlines() if not line.endswith(" binary")]
        lines = [line.replace("eol=crlf", "eol=lf") for line in lines]
        lines = [line for line in lines if not line.startswith("* ")]
        text = "* text=auto eol=lf\n" + "\n".join(lines) + "\n"
        changes.append("text-only-lf-attributes")
    if relative in ("AGENTS.md", "CLAUDE.md"):
        text, count = re.subn(r"(?ms)^## 환경\n.*?(?=^## 보고 형식\n)", lambda _: STUDENT_ENVIRONMENT, text)
        if count != 1:
            raise ValueError(f"Expected one environment section: {relative}")
        text = text.replace("이며 이미 로그인되어 있다.", "이다. 사용할 환경에 CLI를 설치하고 로그인한다.")
        changes.append("portable-environment-and-login")
    if relative == "tools/codex-crosscheck.sh":
        text = text.replace("# Codex는 이미 로그인되어 있다(ChatGPT). MCP 서버는 필요 없다.",
                            "# 사용할 셸에서 Codex CLI를 설치하고 자신의 계정으로 로그인한다. MCP 서버는 필요 없다.")
        changes.append("explicit-cli-login")
    if relative == "tools/check-workspace.py":
        writer = '}, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")'
        portable_writer = '}, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8", newline="\\n")'
        if text.count(writer) + text.count(portable_writer) != 1:
            raise ValueError("Expected one workspace manifest writer")
        if writer in text:
            text = text.replace(writer, portable_writer)
            changes.append("portable-manifest-newline")
    if relative == "docs/BOOTSTRAP.md":
        text = re.sub(r"(?ms)^## 전체 이력\n.*\Z", "", text)
        text = re.sub(r"(?m)^  현재 개발 이력에는.*\n  소스만으로.*\n  재작성은.*\n",
                      "  학생 배포는 검토한 현재 파일만으로 시작한 별도 Git 저장소를 사용한다.\n", text)
        changes.append("student-doc-scope")
    if relative == "docs/STUDENT-GUIDE.md":
        text, count = re.subn(r"(?ms)^## 10\. 벤치마크 수업\n.*?(?=^## 11\.)", STUDENT_BENCHMARK, text)
        if count != 1:
            raise ValueError("Expected one student benchmark lesson section")
        text = re.sub(r"(?m)^학생 URL은 강사의 개발 저장소와.*(?:\n(?!\n).*)*\n",
                      "학생 URL은 검토한 현재 파일만으로 시작한 별도 Git 저장소여야 합니다.\n"
                      "강사가 공지한 학생 저장소와 커밋만 사용합니다.\n", text)
        changes.append("student-benchmark-lesson")
    if relative == "docs/TROUBLESHOOTING.md":
        text = text.replace("`/mnt/e/_/Orca/Projects/ctf-workspace`", "`/mnt/c/CTF-Class/ctf-workspace` (clone 위치에 맞춰 변경)")
        changes.append("portable-repo-example")
    if relative == "docs/INTEGRATIONS.md":
        text = re.sub(r"(?ms)^## 현재 단말 상태.*?(?=^## 설치와 연결\n)", "", text)
        text = text.replace("현재 단말에서는 관리자 PowerShell에서 복구 스크립트를 실행한다.",
                            "WSL 서비스가 종료 대기에 멈춘 경우에만 관리자 PowerShell에서 복구 스크립트를 실행한다.")
        changes.append("portable-integration-guide")
    return text, changes


def inspect_text(relative: str, text: str) -> None:
    if "\x00" in text:
        raise ValueError(f"Binary content is forbidden: {relative}")
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            # Only report a path and category, never echo a matching credential.
            raise ValueError(f"Possible {label} in selected asset: {relative}")
    if re.search(r"(?i)(?:/mnt/e/_/Orca|E:[/\\]_[/\\]Orca|\bdime9\b|이미 로그인되어|already logged in)", text):
        raise ValueError(f"Personal path or login assumption remains: {relative}")


def check_local_markdown_links(files: dict[str, bytes]) -> None:
    """Check local Markdown link files outside fenced and inline code."""
    for relative, data in files.items():
        if not relative.endswith(".md"):
            continue
        fence = None
        for number, line in enumerate(data.decode("utf-8").splitlines(), 1):
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
                if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                    continue
                combined = PurePosixPath(relative).parent / target
                parts = []
                for part in combined.parts:
                    if part == "..":
                        if not parts:
                            raise ValueError(f"Local Markdown link escapes export: {relative}:{number}")
                        parts.pop()
                    elif part not in ("", "."):
                        parts.append(part)
                if "/".join(parts) not in files:
                    raise ValueError(f"Broken exported Markdown link: {relative}:{number} -> {target}")


def plan_export(root: Path) -> tuple[dict[str, bytes], dict]:
    files = {}
    entries = []
    for relative in selected_files(root):
        raw = checked_relative(root, relative).read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ValueError(f"Selected asset is not UTF-8 text: {relative}") from error
        # Inspect original source as well; normalizations may not conceal secrets.
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                raise ValueError(f"Possible {label} in selected source asset: {relative}")
        text, changes = normalize(relative, text)
        inspect_text(relative, text)
        output = text.encode("utf-8")
        files[relative] = output
        entries.append({"source_path": relative, "output_path": relative,
                        "source_sha256": sha256(raw), "output_sha256": sha256(output),
                        "output_bytes": len(output), "transformations": changes})
    # Line endings affect the managed skill manifest; regenerate hashes from the export.
    workspace = json.loads(files["tools/workspace-manifest.json"])
    skill_hashes = {relative.removeprefix(".claude/skills/"): sha256(data)
                    for relative, data in files.items() if relative.startswith(".claude/skills/")}
    for relative, expected in skill_hashes.items():
        if sha256(files.get(".agents/skills/" + relative, b"")) != expected:
            raise ValueError(f"Canonical/mirror mismatch before export: {relative}")
    # Retain reviewed manifest key order so offline setup is byte-idempotent on
    # the source platform; Path sorting in the checker is platform dependent.
    reviewed_order = [rel for rel in workspace.get("skill_sha256", {}) if rel in skill_hashes]
    reviewed_order.extend(sorted(skill_hashes.keys() - set(reviewed_order)))
    workspace["skill_sha256"] = {rel: skill_hashes[rel] for rel in reviewed_order}
    files["tools/workspace-manifest.json"] = (json.dumps(workspace, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    for entry in entries:
        if entry["output_path"] == "tools/workspace-manifest.json":
            data = files[entry["output_path"]]
            entry.update(output_sha256=sha256(data), output_bytes=len(data))
            entry["transformations"].append("normalized-skill-hashes")
    check_local_markdown_links(files)
    manifest = {"schema_version": SCHEMA_VERSION, "source": "reviewed working files; source Git history excluded",
                "git_initialized": False, "file_count_excluding_manifest": len(entries),
                "excluded": ["source Git history", "PPT/POT/PDF and presentation assets",
                             "benchmarks and raw runs", "private seed and credentials",
                             "actual events", "internal audit/worklog documents", ".claude/settings.json",
                             "integration runtimes and generated MCP configuration"],
                "files": entries}
    files[MANIFEST_NAME] = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return files, manifest


def export(root: Path, destination: Path) -> dict:
    check_no_links(root)
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Source root must be a directory")
    check_no_links(destination)
    destination = destination.resolve()
    dist = root / "dist"
    check_no_links(dist)
    if destination == dist or not destination.is_relative_to(dist):
        raise ValueError("Destination must be a child of the source workspace's dist directory")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError("Destination must be absent or an empty directory; existing files are never replaced")
    files, manifest = plan_export(root)
    # The complete allowlist and content checks pass before the first write.
    destination.mkdir(parents=True, exist_ok=True)
    for relative, data in files.items():
        target = checked_relative(destination, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        check_no_links(target)
        with target.open("xb") as stream:
            stream.write(data)
    for relative, data in files.items():
        if checked_relative(destination, relative).read_bytes() != data:
            raise ValueError(f"Export verification failed: {relative}")
    return {"destination": str(destination), "files": len(files), "manifest": MANIFEST_NAME,
            "git_initialized": False, "manifest_sha256": sha256(files[MANIFEST_NAME]),
            "transformed_files": sum(bool(item["transformations"]) for item in manifest["files"])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--destination", type=Path, help="empty child directory inside root/dist (default: dist/student-repo)")
    parser.add_argument("--check-only", action="store_true", help="validate and describe planned export without writing")
    args = parser.parse_args()
    try:
        if args.check_only:
            check_no_links(args.root)
            files, manifest = plan_export(args.root.resolve(strict=True))
            result = {"files": len(files), "git_initialized": False,
                      "transformed_files": sum(bool(item["transformations"]) for item in manifest["files"]),
                      "manifest_sha256": sha256(files[MANIFEST_NAME]), "check_only": True}
        else:
            result = export(args.root, args.destination or args.root / "dist/student-repo")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
