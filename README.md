# CTF Workspace

Claude Code와 Codex로 CTF 대회를 치르기 위한, 재현 가능하고 이식성 있는
워크스페이스입니다. 검증된 스킬 라이브러리, 공유 운영 규칙, 리뷰 준비된
서브에이전트, 그리고 한 커맨드로 구성되는 격리 Linux 툴체인을 묶어 — 어떤
머신에서든, 어떤 에이전트든 동일한 환경을 처음부터 재현할 수 있습니다.

**무엇이 들어 있나**
- **11개 CTF 스킬** (web, pwn, crypto, reverse, forensics, malware, osint, misc,
  ai-ml, writeup) — [ljagiello/ctf-skills](https://github.com/ljagiello/ctf-skills)
  를 핀 고정 커밋으로 벤더링. `solve-challenge` 가 챌린지를 분류해 올바른 스킬로
  라우팅.
- **공유 규칙** — Claude Code(`CLAUDE.md`)와 Codex(`AGENTS.md`)용: 가설 기반 풀이
  루프, 15분 전환 룰, 사전 인테이크, 플래그 처리, Claude↔Codex 교차검증.
- **서브에이전트** (`.claude/agents/`): `triager`, `solver`, `verifier`.
- **전용 Linux 툴체인** — Ubuntu + Python 3.12 venv(pwntools, angr, volatility3
  등)를 `tools/wsl/` 와 동결 requirements 파일로 재현.

대회별 챌린지 데이터와 플래그는 **절대 추적되지 않습니다** — 툴링과 설정만
리포와 함께 이동합니다. 처음이신가요? `docs/BOOTSTRAP.md` 부터 보세요.

## 구성
- `CLAUDE.md` / `AGENTS.md` — Claude Code / Codex 운영 규칙 (동일 내용).
- `.claude/skills/` — 벤더된 11개 CTF 스킬 (디스패처: `solve-challenge`).
- `.claude/agents/` — `triager`, `solver`, `verifier` 서브에이전트.
- `.claude/settings.json` — 도구 권한.
- `events/` — `_TEMPLATE/` 만 포함; 대회별 폴더는 gitignore.
- `tools/` — `new-challenge.sh`, `codex-crosscheck.sh`, `wsl/`, 벤더된 스크립트.
- `tools/wsl/` — 전용 CTF Linux: `setup-ubuntu-ctf.ps1`,
  `provision-ubuntu-ctf.sh`, `ctf-venv-requirements.txt` (동결 툴체인).
- `docs/BOOTSTRAP.md` — 개념 + 새 환경에서 단계별 재구축.
- `docs/WORKLOG.md` — 날짜별 구축 기록. `docs/PRE-CTF-INTAKE.md` — 대회 시작 질문.
- `setup.ps1` — 핀 고정 커밋에서 벤더된 스킬을 재설치.

## 빠른 시작 (대회별)
1. `events/_TEMPLATE/` 를 `events/<대회>/` 로 복사하고, `docs/PRE-CTF-INTAKE.md`
   를 따라 `NOTES.md` 를 채운다 (AI 도구 규칙, 플래그 포맷, 범위).
2. `bash tools/new-challenge.sh <대회> <이름>` 으로 각 챌린지 골격을 만든다.
3. `solve-challenge` 로 분류하거나 `triager` 서브에이전트를 실행 — 모든 단계를
   챌린지 NOTES.md 에 기록한다.
4. `verifier` 가 플래그를 검사하고, 사람이 제출한다. 막혔다면
   `tools/codex-crosscheck.sh` 로 Codex의 독립 의견을 받는다.

## 다른 머신 / 다른 에이전트로 이식
이 리포는 자기완결적이고 경로에 독립적입니다 — 어디에 clone하든 에이전트가 전체
환경을 재구축할 수 있습니다. `docs/BOOTSTRAP.md` 가 개념과 플랫폼별 재구축 절차
(Windows/WSL, 네이티브 Linux, macOS, 컨테이너)를 설명합니다. 챌린지 데이터는
gitignore되므로 툴링과 설정만 리포와 함께 이동합니다.
