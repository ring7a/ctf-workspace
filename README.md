# CTF Workspace

REA/Ghidra의 설치·실행은 [통합 안내](docs/INTEGRATIONS.md)를 따릅니다.

Claude Code와 Codex의 CTF 풀이 지시·도구·증거 기록을 함께 관리하는
워크스페이스입니다. 스킬, 운영 규칙, 서브에이전트, 전용 Linux 설치 스크립트를
공유합니다. Windows/WSL 중심으로 구축했으며, 다른 OS의 툴체인은 별도 검증이
필요합니다. 파일 검증 통과와 실제 문제 풀이 성능은 구분해서 측정합니다.

**무엇이 들어 있나**
- **11개 CTF 스킬** (web, pwn, crypto, reverse, forensics, malware, osint, misc,
  ai-ml, writeup) — [ljagiello/ctf-skills](https://github.com/ljagiello/ctf-skills)
  를 핀 고정 커밋으로 벤더링. `solve-challenge` 가 챌린지를 분류해 올바른 스킬로
  라우팅.
- **공유 규칙** — Claude Code(`CLAUDE.md`)와 Codex(`AGENTS.md`)용: 가설 기반 풀이
  루프, 15분 전환 룰, 사전 인테이크, 플래그 처리, Claude↔Codex 교차검증.
- **서브에이전트** (`.claude/agents/`, `.codex/agents/`): `triager`, `solver`, `verifier`.
- **전용 Linux 툴체인** — Ubuntu + Python 3.12 venv(pwntools, angr, volatility3
  등)를 `tools/wsl/` 와 동결 requirements 파일로 재현.

학생 배포는 **검토된 Git 저장소의 고정 커밋**을 clone/fetch하는 방식으로 합니다.
강사가 제공한 저장소 URL과 전체 커밋 ID를 사용하고, 태그를 받았더라도 해당 커밋과
일치하는지 확인합니다. [학생 저장소 받기](docs/STUDENT-GUIDE.md#2-학생-저장소-받기)와
[단말 설치 절차](docs/BOOTSTRAP.md)를 순서대로 따르세요.

학생 저장소에는 이벤트 데이터·실플래그, 벤치마크 원시 실행 자료, 자격증명,
강사용 PPT를 포함하지 않습니다. `.gitignore`는 이미 추적된 파일이나 과거 이력을
제거하지 않으므로 배포 담당자는 공개할 파일과 Git 이력을 함께 검토해야 합니다.
아직 커밋·게시되지 않은 로컬 변경은 학생의 clone에 포함되지 않습니다.

## 구성
- `CLAUDE.md` / `AGENTS.md` — Claude Code / Codex 운영 규칙 (동일 내용).
- `.claude/skills/` — 벤더된 11개 CTF 스킬 (디스패처: `solve-challenge`).
- `.agents/skills/` — 같은 스킬의 Codex 노출본. 관리 원본은 `.claude/skills/`.
- `.claude/agents/` — `triager`, `solver`, `verifier` 서브에이전트.
- `.codex/agents/` — Codex용 3개 역할 TOML. 모델·계정·로그인은 학생 환경에서 선택.
- `.claude/settings.json` — 도구 권한.
- `events/` — `_TEMPLATE/` 만 포함; 대회별 폴더는 gitignore.
- `tools/` — `new-challenge.sh`, `codex-crosscheck.sh`, `wsl/`, 벤더된 스크립트.
- `tools/volatility/` — 메모리 포렌식 하네스: `vol.ps1`/`vol.sh` 래퍼, 자체 생성 리눅스 ISF,
  커널 키링 플러그인, BTF→ISF 생성·LUKS2 복호 스크립트. 운영 규칙은 "메모리 이미지는 Volatility 먼저".
- `tools/wsl/` — 전용 CTF Linux: `setup-ubuntu-ctf.ps1`,
  `provision-ubuntu-ctf.sh`, `ctf-venv-requirements.txt` (동결 툴체인).
- `docs/BOOTSTRAP.md` — 개념 + 새 환경에서 단계별 재구축.
- `docs/WORKLOG.md` — 날짜별 구축 기록. `docs/PRE-CTF-INTAKE.md` — 대회 시작 질문.
- `setup.ps1` — offline 검사·스킬 미러 동기화. `-FetchUpstream`은 원본 검토용 다운로드.
- `tools/check-workspace.py` / `tools/workspace-manifest.json` — 미러·경로·역할·SHA-256 검사.
- `docs/SKILL-INTEGRATION.md` — upstream 예제에 적용하는 로컬 실행·증거 규칙.
- `docs/REVIEW-2026-10-12.md` — 기존 구현 검토 근거와 보완 범위.

## 빠른 시작 (대회별)

먼저 [BOOTSTRAP](docs/BOOTSTRAP.md)으로 전용 Linux와 모델 CLI 로그인을 준비하고
저장소 루트에서 `python -I tools/check-workspace.py`를 실행합니다(Python 3.11+).

1. `events/_TEMPLATE/` 를 `events/<대회>/` 로 복사하고, `docs/PRE-CTF-INTAKE.md`
   를 따라 `NOTES.md` 를 채운다 (AI 도구 규칙, 플래그 포맷, 범위).
2. `bash tools/new-challenge.sh <대회> <이름>` 으로 각 챌린지 골격을 만든다.
3. `solve-challenge` 로 분류하거나 `triager` 서브에이전트를 실행 — 모든 단계를
   챌린지 NOTES.md 에 기록한다.
4. `verifier` 가 플래그를 검사하고, 사람이 제출한다. 막혔다면
   `tools/codex-crosscheck.sh` 로 Codex의 독립 의견을 받는다.

## 다른 머신 / 다른 에이전트로 이식
스킬·역할 파일은 저장소와 함께 이동하고, CLI 인증·모델 이용 권한·WSL 등록·대회
자료는 별도로 준비합니다. 새 경로에 맞춰 운영 규칙의 환경 설명을 확인하세요.
기본 `setup.ps1`은 네트워크 없이 미러를 갱신하며, 직접 수정된 Codex 미러는
덮어쓰지 않고 중단합니다. 원본 `.claude/skills/`에 변경을 합친 뒤 다시 실행합니다.

프롬프트 규칙은 행동 지침입니다. WSL·Gitignore·역할 이름만으로 모든 접근 범위와
증거 기록이 자동 강제되지는 않습니다. 자세한 보장 범위는 검토 보고서를 참고하세요.

## 학생 안내와 검토 자료

- [학생 실습·설치 안내](docs/STUDENT-GUIDE.md)
- [전체 구성·프롬프트 검토](docs/REVIEW-2026-10-12.md), [구현 감사·의존성·회귀 검사](docs/IMPLEMENTATION-AUDIT-2026-10-12.md)
- [벤치마크 설계·실행 상태](benchmarks/README.md) — 현재 러너 준비·정적 검사 단계. Claude 단독·Codex 단독·프로젝트 하네스의 3조건 실측 결과는 아직 없다.

기준 커밋에는 과거 발표 생성기 3개가 있었지만 학생 저장소 정리 과정에서 제거했다.
그 자료의 기록 건수·설치 시간·효과 주장을 현재 벤치마크 결과로 사용하지 않는다.
강사용 발표 파일과 생성기는 학생 Git 배포에 포함하지 않으며, 학생은 저장소의
실습 안내와 위 감사 자료를 사용한다.

현재 개발 저장소의 과거 7개 커밋에는 `docs/CTF-Setup-Deck.pptx`가 남아 있다.
따라서 이 개발 원격을 그대로 학생에게 공개하지 않는다. 검토된 현재 소스만으로
새 이력을 시작한 별도 학생 저장소를 만들고, 그 저장소의 전체 커밋 ID를 공지한다.
