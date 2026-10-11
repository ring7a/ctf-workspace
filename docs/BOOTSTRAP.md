# BOOTSTRAP — 새 환경에서 이 CTF 워크스페이스 재구축하기

대상 독자: 새 머신에서 이 워크스페이스를 세팅하는 Claude Code(또는 Codex)
에이전트. 위에서 아래로 읽은 뒤, 당신 플랫폼에 해당하는 단계를 실행하세요.
여기 있는 모든 것은 이미 이 리포에 있는 파일들로 재현 가능합니다.

## 개념 (이 워크스페이스가 무엇인가)

네 개의 레이어로 된 이식 가능한 CTF 대회 워크스페이스:

1. **지식 레이어 — 벤더된 스킬.** `.claude/skills/` 에 `ljagiello/ctf-skills`
   의 11개 CTF 스킬이 커밋으로 핀 고정되어 있다. `solve-challenge` 가 디스패처:
   챌린지를 분류해 카테고리 스킬(`ctf-web`, `ctf-pwn`, `ctf-crypto`,
   `ctf-reverse`, `ctf-forensics`, `ctf-malware`, `ctf-osint`, `ctf-misc`,
   `ctf-ai-ml`)과 `ctf-writeup` 으로 라우팅한다.
2. **규칙 레이어.** `CLAUDE.md`(Claude Code)와 동일한 `AGENTS.md`(Codex)가
   운영 루프를 정의한다: 정찰 -> 가설 하나 -> 최소 검증 -> NOTES.md 기록 ->
   다음; 15분 전환 룰; 플래그 처리; Claude+Codex 교차검증 프로토콜.
3. **자동화 레이어 — 서브에이전트.** `.claude/agents/`: `triager`(정찰/분류,
   읽기 전용), `solver`(격리된 worktree에서 한 챌린지를 끝까지), `verifier`
   (플래그 포맷 + 재현성, 읽기 전용).
4. **런타임 레이어 — 격리 Linux.** 신뢰할 수 없는 챌린지 바이너리는 호스트가
   아니라 CTF 툴체인을 갖춘 전용 Linux 환경 안에서만 실행한다. 정확한 패키지
   집합은 `tools/wsl/ctf-venv-requirements.txt` 에 동결되어 있다.

설계 원칙: 메인 세션 컨텍스트를 깨끗하게 유지(서브에이전트 + worktree에 위임);
모든 풀이를 재현 가능하게(명령은 챌린지 NOTES.md에 기록); 관심사 분리(전용 CTF
Linux, 호스트 개발 머신은 건드리지 않음); 스킬을 벤더링 + 핀 고정해 환경을
결정적으로.

## 버전관리 대상 vs 아닌 것

- 추적: 스킬, 규칙, 에이전트, 설정, tools/스크립트, 문서, 이벤트 NOTES 템플릿.
  이것이 전체 세팅 — 재구축에 충분하다.
- 무시(`.gitignore`): `events/*/challenges/` 전체 (챌린지 데이터와 풀이 작업은
  대회별이고, 신뢰 불가이며, 크거나 바이너리인 경우가 많다).

## 재구축 단계

### 0. 리포 받기
clone(또는 폴더 복사). 아래 모든 경로는 리포 루트 기준 상대 경로이며, 어디에
두든 상관없다.

### 1. 스킬 (모든 플랫폼)
스킬은 이미 `.claude/skills/` 아래 벤더링되어 있다. 핀 고정된 업스트림 커밋에서
새로 받으려면: `pwsh -File setup.ps1` (Windows) — Linux/mac에서는
`tools/vendor-ctf-skills/PINNED_COMMIT.txt` 의 커밋으로 `ljagiello/ctf-skills`
를 clone하고 그 `ctf-*` 및 `solve-challenge` 폴더를 `.claude/skills/` 로 복사.
리포 루트에서 Claude Code를 열면 `.claude/` 를 자동 발견한다.

### 2. 격리 CTF Linux + 툴체인

**Windows + WSL2** (이 리포가 구축된 환경):
- `pwsh -File tools\wsl\setup-ubuntu-ctf.ps1`
  전용 `ubuntu-ctf` 배포판을 import하고 프로비저닝한다
  (`tools\wsl\provision-ubuntu-ctf.sh`): 사용자 `ctf`, apt 분석 도구, 그리고
  동결 requirements에서 설치한 Python 3.12 venv(`uv` 사용).
- `wsl -d ubuntu-ctf` 로 진입; CTF venv가 자동 활성화된다.

**네이티브 Linux / macOS / 컨테이너:** `.ps1` 은 필요 없다. 툴체인을 직접 재현:
```bash
# 시스템 도구 (Debian/Ubuntu 예시)
bash tools/vendor-ctf-skills/scripts/install_ctf_tools.sh apt
# python 툴체인 — Python 3.12 사용 (3.13/3.14 금지: 휠 없음, angr 빌드 실패)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
uv venv --python 3.12 ~/.ctf-tools/venv
VIRTUAL_ENV=~/.ctf-tools/venv uv pip install -r tools/wsl/ctf-venv-requirements.txt
echo '[ -f ~/.ctf-tools/venv/bin/activate ] && source ~/.ctf-tools/venv/bin/activate' >> ~/.bashrc
```
RPM 계열 배포판에서는 설치 스크립트의 다른 모드를 사용; Python 부분은 동일하다.

### 3. Codex 협업 (선택이지만 권장)
Claude가 2차 의견을 받을 수 있도록 Codex를 MCP 서버로 등록:
`pwsh -File tools\register-codex-mcp.ps1` (또는 `claude mcp add codex --scope
project -- codex mcp-server`). `AGENTS.md` == `CLAUDE.md` 를 유지한다.

### 4. 대회별
- `events/<대회>/NOTES.md` 에 플래그 포맷/정규식, 서버 범위, 참가 규정의 AI 도구
  규칙을 채운다.
- `bash tools/new-challenge.sh <대회> <이름>` 으로 각 챌린지 골격 생성
  (`untrusted/` 은 원본, `work/` 는 작업, NOTES.md).

## 어렵게 얻은 함정들 (다시 발견하지 말 것)
- **Python 3.14는 툴체인을 깨뜨림**: 여러 핀에 cp314 휠이 없고, angr의 pyvex가
  빌드되지 않는다. **Python 3.12** 를 사용.
- **angr import 오류** (`CLexer ... no setter`): `pycparser==2.22` 로 핀 고정.
- **fpylll import 오류** (`No module named cysignals`): `pip install cysignals`.
- **uv는 원자적으로 해석**: 하나의 잘못된 핀(예: 존재하지 않는 버전)이 전체
  설치를 중단시킨다. 폴백과 함께 패키지별로 설치하거나, 검증된 동결 requirements
  를 사용.
- **Windows의 Git은 CRLF를 추가**: Linux 안에서 셸 스크립트를 실행하기 전에
  `\r` 를 제거 (`sed -i 's/\r$//' script.sh`).

## 전체 이력
`docs/WORKLOG.md` 에 날짜별 상세 기록이 있고, 원시 로그는 `docs/wsl-logs/`
아래에 있다.
