# BOOTSTRAP — 새 환경에서 이 CTF 워크스페이스 재구축하기

대상 독자: 새 머신에서 이 워크스페이스를 세팅하는 Claude Code(또는 Codex)
에이전트. 위에서 아래로 읽은 뒤, 당신 플랫폼에 해당하는 단계를 실행하세요.
스킬·역할·규칙은 리포로 옮기고, 모델 로그인·OS 설치·대회 데이터는 별도로 준비합니다.
현재 검증 범위와 학생 단말에서 새로 확인할 항목을 아래에서 구분합니다.

## 개념 (이 워크스페이스가 무엇인가)

네 개의 레이어로 된 이식 가능한 CTF 대회 워크스페이스:

1. **지식 레이어 — 벤더된 스킬.** `.claude/skills/` 원본과 `.agents/skills/` 미러에 `ljagiello/ctf-skills`
   의 11개 CTF 스킬이 커밋으로 핀 고정되어 있다. `solve-challenge` 가 디스패처:
   챌린지를 분류해 카테고리 스킬(`ctf-web`, `ctf-pwn`, `ctf-crypto`,
   `ctf-reverse`, `ctf-forensics`, `ctf-malware`, `ctf-osint`, `ctf-misc`,
   `ctf-ai-ml`)과 `ctf-writeup` 으로 라우팅한다.
2. **규칙 레이어.** `CLAUDE.md`(Claude Code)와 동일한 `AGENTS.md`(Codex)가
   운영 루프를 정의한다: 정찰 -> 가설 하나 -> 최소 검증 -> NOTES.md 기록 ->
   다음; 15분 전환 룰; 플래그 처리; Claude+Codex 교차검증 프로토콜.
3. **역할 레이어 — 서브에이전트.** `.claude/agents/`와 `.codex/agents/`:
   `triager`(정찰/분류), `solver`(한 챌린지), `verifier`(형식 + 재현성).
   호출자가 소유 경로를 지정한다. 역할 이름만으로 worktree가 생성되지는 않는다.
4. **런타임 레이어 — 격리 Linux.** 신뢰할 수 없는 챌린지 바이너리는 호스트가
   아니라 CTF 툴체인을 갖춘 전용 Linux 환경 안에서만 실행한다. 정확한 패키지
   집합은 `tools/wsl/ctf-venv-requirements.txt` 에 동결되어 있다.

설계 원칙: 서브에이전트에 범위와 산출물을 지정하고, 명령·증거는 challenge NOTES에
남긴다. 원본/작업 디렉터리와 전용 Linux를 분리하고, 의존성과 지시를 버전 관리한다.
이는 전용 분석 환경이지 완전한 악성코드 보안 경계가 아니다. WSL의 `/mnt` 마운트,
Windows interop, 네트워크와 Docker 권한은 별도로 확인해야 한다.

## 버전관리 대상 vs 아닌 것

- 배포 대상: 검토된 두 제품의 스킬·역할, 규칙, 설정, tools/스크립트, 학생 문서, 이벤트 템플릿.
- 제외 대상: 템플릿 외 이벤트 데이터·실플래그·문제 원본, 벤치마크 원시 실행 자료,
  토큰·CLI 로그인 파일 등 자격증명, 강사용 PPT와 렌더 산출물.
- `git status --short`의 미추적 파일은 commit 전 원격 clone에 포함되지 않는다.
  배포 담당자가 필요한 파일과 도달 가능한 Git 이력을 검토해 게시한 뒤 학생에게
  저장소 URL과 전체 커밋 ID를 전달한다. `.gitignore`는 강제 추가나 이미 추적된
  비밀·과거 이력을 제거하지 않는다. 강사 개인 작업 저장소를 그대로 공개하지 않는다.
  현재 개발 이력에는 과거 발표 PPT blob이 남아 있으므로, 학생 배포에는 검토한 현재
  소스만으로 시작한 별도 clean-history 저장소를 사용한다. 기존 개발 이력의 강제
  재작성은 이 절차에서 수행하지 않는다.

## 재구축 단계

### 0. 리포 받기
학생 배포는 Git clone/fetch로만 받는다. 강사에게 받은 `<학생용-저장소-URL>`과
`<검토된-전체-커밋-ID>`를 사용한다. 태그를 제공받았다면 그 태그가 가리키는 전체
커밋 ID도 함께 받아 대조한다. 태그 이름만으로 내용이 고정됐다고 가정하지 않는다.
[학생 안내의 clone·fetch·커밋 검증 절차](STUDENT-GUIDE.md#2-학생-저장소-받기)를 따른다.
원격 URL과 배포 커밋은 이 문서에서 임의로 정하지 않으며, 로컬 변경이 원격에 게시된
상태라고 가정하지 않는다. 검증된 커밋을 detached HEAD로 받은 뒤 모든 설치 명령은
리포 루트에서 실행한다. 업데이트도 검토된 새 커밋을 fetch하고 같은 검증을 반복한다.
`CLAUDE.md`/`AGENTS.md`의 환경 설명에 예전 머신 경로가 있으면 현재 clone 경로와
배포판 이름에 맞춘다. 계정·토큰은 저장소에 복사하지 않는다.

필요 조건: Git, Windows PowerShell 5.1 또는 PowerShell 7, WSL2가 가능한 Windows와
가상화 설정, Ubuntu rootfs 또는 Ubuntu 앱 설치, 사용할 모델 CLI와 해당 계정 권한.
정적 검사에는 Python 3.11+가 필요하다. 호스트 Python이 없으면 먼저 2단계를 마친
뒤 `ubuntu-ctf` 안에서 검사한다. PowerShell 7의 `pwsh`가 없으면 아래의
`powershell -File` 명령을 사용한다.

### 1. 스킬 (모든 플랫폼)
스킬은 이미 두 제품의 발견 경로에 포함되어 있다. 원본을 다시 다운로드할 필요는 없다.

```powershell
# Windows: offline 미러 동기화 + 정적 검사 (Python 3.11+ 필요)
powershell -File setup.ps1
```

```bash
# Linux/macOS에서도 같은 자산 검사. Python 3.11+ 필요.
python3 -I tools/check-workspace.py
# 원본을 수정한 뒤, 관리된 미러만 갱신
python3 -I tools/check-workspace.py --sync
```

`.claude/skills/`만 편집한다. 미러에 직접 수정한 파일이 있으면 `--sync`는 중단하며
그 파일을 보존한다. 변경을 원본에 병합한 뒤 재실행한다. CLAUDE/AGENTS 운영 규칙과
두 제품의 역할 파일은 제품별 파일이므로 별도로 검토한다. 스킬 파일 SHA-256만
`tools/workspace-manifest.json`에 기록한다.

Claude는 `.claude/skills/`, Codex는 `.agents/skills/`를 발견한다. Codex 역할은
`.codex/agents/*.toml`의 name/description/developer_instructions 형식이다.
새 세션에서 11개 CTF 스킬과 3개 역할이 보이는지 확인한다. 실제로 이름을 발견했다는
결과와 정적 검사 결과는 다르므로 둘 다 확인한다.
[공식 스킬 문서](https://learn.chatgpt.com/docs/build-skills),
[공식 역할 문서](https://learn.chatgpt.com/docs/agent-configuration/subagents).

### 2. 격리 CTF Linux + 툴체인

**Windows + WSL2** (이 리포가 구축된 환경):
- `powershell -File tools\wsl\setup-ubuntu-ctf.ps1`
  전용 `ubuntu-ctf` 배포판을 import하고 프로비저닝한다
  (`tools\wsl\provision-ubuntu-ctf.sh`): 사용자 `ctf`, apt 분석 도구, 그리고
  동결 requirements에서 설치한 Python 3.12 venv(`uv` 사용).
- `wsl -d ubuntu-ctf` 로 진입; CTF venv가 자동 활성화된다.
- Ubuntu 앱 rootfs를 찾지 못하면 다운로드 출처와 무결성을 확인한 rootfs를
  `-Tarball C:\path\ubuntu-rootfs.tar.gz`로 지정한다. 기존 배포판을 덮어쓰지 않는다.
  새 배포판이 필요하면 `-Distro`와 `-InstallDir`를 명시한다.
- 설치 후 전용 배포판에서 `python -V`, 필요한 모듈 import,
  `docker version`(컨테이너 문제 사용 시), `tmux -V`를 확인한다.
- 가용 디스크, 가상화, WSL 업데이트/재부팅, 다운로드 속도는 단말마다 다르다.
  이 절차를 새 머신에서 완료하는 데 걸리는 시간은 아직 보장하지 않는다.

**네이티브 Linux / macOS / ARM:** 스킬·역할·정적 검사 자산은 사용할 수 있으나
전체 툴체인 설치는 검증되지 않았다. 수업의 동일 조건이 필요하면 별도 Ubuntu VM을
준비하고 x86-64 도구/문제 실행 가능 여부를 확인한다. apt 명령을 macOS에 그대로
실행하지 않는다. 동결된 Python 패키지 목록도 모든 OS·CPU의 wheel을 보장하지 않는다.

### 3. 두 모델과 교차검증
Claude Code와 Codex CLI를 사용할 실행 환경에 각각 설치하고 로그인한다.
`claude --version`, `codex --version`, `codex login status`로 확인한다.
호스트 로그인과 WSL 로그인은 서로 다른 환경일 수 있다. 인증 파일을 공유 리포에
복사하는 방식으로 해결하지 않는다.

이 저장소의 교차검증 경로는 MCP가 아니라 CLI wrapper다:

```bash
bash tools/codex-crosscheck.sh "현재 가설과 그것을 반증하는 증거"
bash tools/codex-crosscheck.sh --review
```

실제 지원 옵션·추가 작업 경로는 wrapper의 도움말을 확인한다. 리뷰 대상이 Git에서
무시된 challenge work라면 결과에 그 파일이 포함되었는지 확인해야 한다.
Codex가 주도할 때도 같은 규칙·스킬·역할을 사용한다. Claude의 독립 의견이 필요하면
사용 가능한 Claude 세션에 구체적인 가설·반증·파일 범위를 전달한다. 자동으로
두 모델이 모두 실행된다고 가정하지 않는다.

### 4. 대회별
- `events/<대회>/NOTES.md` 에 플래그 포맷/정규식, 서버 범위, 참가 규정의 AI 도구
  규칙을 채운다.
- `bash tools/new-challenge.sh <대회> <이름>` 으로 각 챌린지 골격 생성
  (`untrusted/` 은 원본, `work/` 는 작업, NOTES.md).
- 첫 실습은 강사가 재배포 권한과 정답을 확인한 로컬 문제로 수행한다. 명령·출력·
  종료 코드·입력 hash를 남기고, 다른 역할이 처음 입력부터 재실행한다.
- 새 단말에서 위 과정과 인간 제출 경계를 확인한 뒤 실제 이벤트에 적용한다.

## 유지보수와 upstream 갱신

`powershell -File setup.ps1 -FetchUpstream`은 pin을 검증한 원본을 임시 **검토 폴더**에
다운로드한다. 기존 스킬이나 vendor 스크립트를 자동 교체하지 않는다. Git 실패 시
즉시 중단하며 검토 폴더는 보존한다. 변경을 비교하고 필요한 부분만 관리 원본에
반영한다. `docs/SKILL-INTEGRATION.md`에 기록한 로컬 수정과 MIT 고지를 보존하고
`python -I tools/check-workspace.py --sync` 후 결과를 검토한다.

## 어렵게 얻은 함정들 (다시 발견하지 말 것)
- **구축 당시 Python 3.14 설치 실패**: 동결 목록의 일부 wheel과 angr 빌드가
  실패했다. 이 툴체인은 **Python 3.12** 기준이다.
- **angr import 오류** (`CLexer ... no setter`): `pycparser==2.22` 로 핀 고정.
- **fpylll import 오류** (`No module named cysignals`): `pip install cysignals`.
- **핀 설치 실패**: 임의의 최신 버전으로 조용히 대체하면 같은 환경이 아니다.
  실패한 패키지·플랫폼을 기록하고 핀 변경은 별도 검토한다.
- **줄바꿈**: `.gitattributes`로 Linux 실행 파일과 스킬 해시 기준을 LF로 유지한다.
  수정 후에는 정적 검사와 필요한 런타임 검사를 다시 실행한다.

## 전체 이력
`docs/WORKLOG.md` 에 날짜별 상세 기록이 있고, 원시 로그는 `docs/wsl-logs/`
아래에 있다.
