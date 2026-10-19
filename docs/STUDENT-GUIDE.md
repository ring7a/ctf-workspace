# 학생용 CTF Workspace 적용 가이드

이 저장소는 Claude Code와 Codex의 CTF 분석을 위한 **지침, 스킬, 실행 도구, 기록 관례**를 묶습니다. 수업에서는 정답뿐 아니라 가설과 반증, 재현 가능한 명령, 독립 검증을 함께 평가합니다. 실제 대회에서는 해당 대회의 AI 사용 규칙과 대상 범위를 먼저 확인합니다.

학생은 검토된 Git 저장소의 코드와 이 안내로 실습합니다. 강사용 PPT는 학생 배포에 포함하지 않습니다.

## 1. 준비 사항

- Windows에서 WSL2를 사용할 수 있어야 합니다. 학교 관리 단말에서는 가상화·WSL·패키지 설치 정책을 강사에게 확인합니다.
- Git for Windows, PowerShell, Claude Code와 Codex CLI를 준비합니다. 이 가이드의 기본 경로는 **Windows에서 CLI를 실행하고 챌린지 분석은 WSL에서 수행**하는 방식입니다. 계정·사용량 정책은 수업 안내를 따릅니다.
- 강사가 검증한 Ubuntu rootfs tarball과 그 SHA-256을 받습니다. 저장소는 OS 이미지 자체를 포함하지 않습니다.
- 패키지를 받을 네트워크와 충분한 디스크 공간을 준비합니다. 모든 플랫폼에 대해 동일하게 검증된 설치는 아닙니다. 이 가이드는 Windows + `ubuntu-ctf` WSL을 기준으로 합니다.

전용 WSL은 Linux 도구와 의존성을 분리합니다. 기본 WSL은 Windows 드라이브와 연동할 수 있고, 이 프로젝트는 관리자 권한·공유 경로·네트워크를 완전히 차단하는 보안 샌드박스를 제공하지 않습니다. 실제 악성코드 등 고위험 샘플의 실행은 강사가 정한 별도 VM·네트워크 통제를 따릅니다.

### Windows CLI 설치와 로그인

PowerShell에서 공식 설치 명령을 실행합니다. 설치 프로그램을 받는 주소와 학교의 설치 정책을 확인한 뒤 실행합니다. 아래 명령은 이 문서를 작성하면서 실제 설치를 수행했다는 뜻이 아닙니다.

```powershell
# Claude Code
irm https://claude.ai/install.ps1 | iex
# Codex CLI
powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"
```

Claude는 `winget install Anthropic.ClaudeCode`, Codex는 Node.js가 준비되어 있다면 `npm install -g @openai/codex`도 공식 대안입니다. 설치 후 새 터미널을 열고 리포 루트에서 `claude`와 `codex`를 각각 실행해 자신의 계정으로 로그인합니다. 버전과 로그인 방식을 수업 기록에 남깁니다. [Claude Code 설치 문서](https://code.claude.com/docs/en/setup), [Codex CLI 설치 문서](https://learn.chatgpt.com/docs/codex/cli)에서 확인한 절차이며, 확인일은 2026-10-12입니다.

이 가이드의 교차 검토 래퍼는 Windows의 Git Bash에서 Windows Codex CLI를 찾는 경로를 기준으로 설명합니다. WSL에 CLI를 설치하는 대안도 있지만, Windows에 설치한 CLI와 Linux에 설치한 CLI의 PATH·로그인·권한은 같은 설정이 아닙니다. 두 방식을 한 실습에서 섞지 않습니다. 이 작업에서는 새 WSL에 양 CLI를 설치하는 전체 경로를 실측하지 않았습니다.

## 2. 학생 저장소 받기

**학생 배포 경로는 Git clone/fetch입니다.** 강사는 학생에게 공개할 파일과 Git 이력을 검토한 저장소 URL, 검토된 커밋 또는 릴리스 태그, 그에 대응하는 **전체 커밋 ID**를 공지합니다. 이 문서의 `<...>`는 실제 값으로 바꿔야 하는 자리표시자입니다. 현재 로컬 변경이 원격에 게시되었다고 가정하지 않으며, 강사가 배포 커밋을 공지한 뒤 진행합니다.

학생 URL은 강사의 개발 저장소와 분리한 clean-history 저장소여야 합니다. 현재 개발 저장소의 과거 이력에는 발표 PPT가 남아 있으므로 그 원격을 그대로 학생에게 제공하지 않습니다. 학생은 강사가 공지한 별도 저장소만 사용하며, 개발 저장소의 이력을 가져오거나 두 원격을 섞지 않습니다.

학생 저장소에는 템플릿을 제외한 이벤트 데이터·실플래그·문제 원본, 벤치마크 원시 실행 폴더·로그·평가 원본, 자격증명, 강사용 PPT·렌더 산출물이 없어야 합니다. 실습 문제는 AI 허용·범위·재배포 권한을 확인한 뒤 해당 실습의 로컬 이벤트 폴더에 별도로 준비합니다. 정리된 벤치마크 설계와 공개 검토를 마친 요약은 원시 실행 자료와 구별합니다.

### 처음 받기

아래 예시는 `C:\CTF-Class\ctf-workspace`가 없는 새 위치를 사용합니다. 강사가 공지한 값을 입력하고 PowerShell에서 실행합니다. 태그는 이동될 수 있으므로, 태그 이름을 받았더라도 별도로 공지한 전체 커밋 ID와 반드시 대조합니다.

```powershell
$studentRepoUrl = '<강사가-제공한-학생용-저장소-URL>'
$reviewedRef = '<검토된-커밋-ID-또는-릴리스-태그>'
$reviewedCommit = '<강사가-공지한-전체-커밋-ID>'
git clone --no-checkout $studentRepoUrl C:\CTF-Class\ctf-workspace
if ($LASTEXITCODE -ne 0) { throw 'clone 실패' }
Set-Location C:\CTF-Class\ctf-workspace
git fetch --no-tags origin $reviewedRef
if ($LASTEXITCODE -ne 0) { throw '검토된 ref 받기 실패' }
$receivedCommit = git rev-parse --verify 'FETCH_HEAD^{commit}'
if ($LASTEXITCODE -ne 0 -or $receivedCommit -ne $reviewedCommit) {
    throw '강사가 공지한 커밋과 일치하지 않습니다. 설치를 중단합니다.'
}
git checkout --detach $reviewedCommit
if ($LASTEXITCODE -ne 0) { throw '검토된 커밋 checkout 실패' }
git rev-parse HEAD
```

마지막 출력이 공지된 전체 커밋 ID와 같아야 합니다. `detached HEAD`는 수업 버전을 고정한 상태라는 뜻이며 오류가 아닙니다. 커밋 ID와 저장소 URL을 실습 기록에 남깁니다. 이 검사는 받은 소스 버전을 확인하며 설치 성공이나 모델의 규칙 준수를 보장하지 않습니다.

### 강사가 공지한 새 버전 받기

리포 루트에서 기존 변경을 먼저 확인합니다. 수정 파일이 있으면 별도로 보존하고 검토한 뒤 진행하며, 강제 덮어쓰기나 reset으로 지우지 않습니다. 강사가 새로 공지한 ref와 전체 커밋 ID를 사용합니다.

```powershell
git remote get-url origin
$pendingChanges = @(git status --porcelain)
if ($LASTEXITCODE -ne 0) { throw '작업트리 상태 확인 실패' }
if ($pendingChanges.Count -ne 0) { throw '로컬 변경을 먼저 보존·검토하세요.' }
$reviewedRef = '<새로-검토된-커밋-ID-또는-릴리스-태그>'
$reviewedCommit = '<새로-공지된-전체-커밋-ID>'
git fetch --no-tags origin $reviewedRef
if ($LASTEXITCODE -ne 0) { throw '검토된 ref 받기 실패' }
$receivedCommit = git rev-parse --verify 'FETCH_HEAD^{commit}'
if ($LASTEXITCODE -ne 0 -or $receivedCommit -ne $reviewedCommit) {
    throw '공지된 새 커밋과 일치하지 않습니다.'
}
git checkout --detach $reviewedCommit
if ($LASTEXITCODE -ne 0) { throw '새 커밋 checkout 실패' }
git rev-parse HEAD
```

`origin` URL이 강사가 공지한 학생 저장소인지 확인합니다. 기본 브랜치의 최신 상태를 자동으로 설치하지 않으며, 받은 커밋과 스킬 정적 검사를 다시 확인합니다. 설치 전에 WSL 상태도 확인합니다.

```powershell
wsl --version
wsl -l -v
```

기존 `ubuntu-ctf`가 있다면 그 환경을 먼저 확인합니다. 새 설치를 위해 기존 배포판을 삭제하거나 `wsl --unregister`할 필요는 없습니다. 강사와 협의해 별도 배포판 이름을 사용하거나 기존 환경을 점검합니다.

## 3. 분석 환경 만들기

받은 이미지 파일의 해시를 강사가 제공한 값과 비교합니다. 파일 경로는 자신의 파일로 바꿉니다.

```powershell
Get-FileHash -Algorithm SHA256 C:\CTF-Images\ubuntu-rootfs.tar.gz
```

새 `ubuntu-ctf`를 만들 때 리포 루트에서 실행합니다.

```powershell
powershell -File tools\wsl\setup-ubuntu-ctf.ps1 -Tarball C:\CTF-Images\ubuntu-rootfs.tar.gz
```

스크립트는 Linux 사용자, 시스템 분석 도구, Python 3.12 venv, tmux와 기본 Docker 구성을 준비합니다. 기존 배포판 재설치는 거부하며 native 명령 실패 시 중단합니다. 설치가 끝났다는 메시지만으로 성공을 판단하지 않고 다음 항목을 점검합니다. OS 이미지·apt 저장소·일부 다운로드까지 완전히 고정한 설치는 아니므로, 사용한 이미지 해시와 설치 로그를 보관합니다. **수정된 설치 경로의 새 단말 전체 설치는 아직 검증하지 않았습니다.**

스킬은 저장소에 포함되어 있으므로 최초 사용을 위해 업스트림에서 다시 받을 필요는 없습니다. 현재 `setup.ps1`의 기본 동작은 **오프라인 검사와 보호된 동기화**입니다. Windows Python 3.11 이상이 있으면 리포 루트에서 다음 명령을 사용합니다.

```powershell
powershell -File setup.ps1
```

Windows Python이 없으면 WSL에서 리포 루트로 이동한 뒤 `python -I tools/check-workspace.py --sync`를 실행합니다. `setup.ps1 -FetchUpstream`은 고정된 업스트림을 별도의 검토 디렉터리에 내려받는 선택 기능이며, 기존 스킬을 그대로 덮어쓰지 않습니다.

## 4. 설치 확인

PowerShell에서 먼저 확인합니다.

```powershell
wsl -l -v
wsl -d ubuntu-ctf -- bash -lc 'id; command -v python; python --version'
wsl -d ubuntu-ctf -- bash -lc 'command -v git; command -v file; command -v gdb; command -v tmux'
wsl -d ubuntu-ctf -- docker info
claude --version
codex --version
```

이후 WSL 셸에 들어가 핵심 import를 확인합니다. 이 명령은 챌린지 파일을 실행하지 않습니다.

```powershell
wsl -d ubuntu-ctf
```

```bash
python -I -c 'import sys, pwn, angr, fpylll, Crypto, z3; print(sys.executable); print(sys.version); print("core imports OK")'
```

Python 경로가 전용 `~/.ctf-tools/venv`를 가리키는지 확인합니다. 패키지별 설치 성공과 CLI 로그인은 별도 항목입니다. import 실패·로그인 오류·할당량 부족은 풀이 실패와 구분해서 기록합니다.

리포 루트의 WSL 셸에서 자산 정합성도 검사합니다.

```bash
python -I tools/check-workspace.py
```

이 검사는 지침·스킬 등의 파일 정합성을 확인합니다. 모델이 모든 규칙을 준수하거나 보안이 보장된다는 증명은 아닙니다.

리포 루트에서 각 에이전트에게 `CLAUDE.md` 또는 `AGENTS.md`, `solve-challenge`, `triager`·`solver`·`verifier`의 발견 경로를 확인하도록 요청합니다. Claude용 `.claude/`와 Codex용 `.agents/skills/`, `.codex/agents/`가 대상입니다. 단순히 파일이 있는 것과 CLI가 실제로 읽는 것은 다른 확인 항목입니다.

## 5. 첫 실습 이벤트 만들기

교실 실습도 인테이크를 생략하지 않습니다. 강사는 **AI 허용, 실습용 플래그 형식, 로컬 파일만 허용하는 범위**를 명시합니다. 학생은 `docs/PRE-CTF-INTAKE.md`를 읽고 템플릿을 채웁니다.

PowerShell에서:

```powershell
Copy-Item -Recurse events\_TEMPLATE events\classroom
```

이미 `events\classroom`이 있으면 복사 명령을 반복하지 말고 그 `NOTES.md`를 사용합니다. 강사가 제공한 허용 규칙과 플래그 형식을 기록한 후 WSL 또는 Bash에서 챌린지 골격을 만듭니다.

```bash
cd /mnt/c/CTF-Class/ctf-workspace
bash tools/new-challenge.sh classroom demo
```

받은 원본은 `events/classroom/challenges/demo/untrusted/`에 넣고 변경하지 않습니다. 분석 코드와 출력은 `work/`에서 만들며, 신뢰할 수 없는 파일의 분석·실행은 `ubuntu-ctf` 내부에서 수행합니다. `untrusted/` 안을 작업 디렉터리로 삼아 인터프리터를 실행하지 않습니다.

```bash
cd events/classroom/challenges/demo/work
sha256sum ../untrusted/sample.bin
python -I decode.py ../untrusted/sample.bin
```

위 `decode.py`는 학생 또는 에이전트가 작성하는 분석 스크립트의 예시입니다. 저장소가 이 파일을 자동 제공한다는 뜻이 아닙니다.

## 6. AI에게 전달할 요청 예시

```text
이 로컬 교육용 문제를 solve-challenge로 정찰해 줘.
규칙과 범위는 events/classroom/NOTES.md에 있어.
문제는 events/classroom/challenges/demo/untrusted/에 있고,
작업 결과는 같은 챌린지의 work/에 저장해 줘.

가설 하나를 세우고 가장 작은 실험으로 확인해 줘.
입력 해시, 명령, 원시 출력, 반증을 NOTES.md에 연결해 줘.
15분 동안 진전이 없으면 접근을 바꾸고 이유를 남겨 줘.
완료 전 verifier가 같은 입력으로 최소 풀이를 재실행하고,
ctf-writeup으로 짧은 풀이 문서를 작성해 줘.
공식 플래그 제출은 내가 할게.
```

작업 중 상태는 `가설 / 확인된 사실 / 다음 실험` 세 줄로 받습니다. 성공한 실험만 정리하지 말고 반증된 가설도 남깁니다.

## 7. Claude와 Codex 협업

주 분석 모델과 검토 모델의 역할은 교체할 수 있습니다. 저장소에는 각 도구의 역할 정의가 있고, Claude에서 Codex의 2차 의견을 받을 때는 셸 래퍼를 사용할 수 있습니다. 현재 방식에 MCP 서버 등록은 필요하지 않습니다.

```bash
bash tools/codex-crosscheck.sh "현재 가설: ... 반증한 관찰: ... 남은 대안을 비교해 줘."
bash tools/codex-crosscheck.sh --review
```

기본 구성에서는 Windows Git Bash를 열고 리포 루트에서 실행합니다. `codex --version`이 그 셸에서 먼저 동작해야 합니다. Windows에만 설치한 CLI가 WSL에 자동 설치되지는 않습니다. 검토 의견은 가설이며, 실제 판별 실험과 재실행으로 확인합니다.

동시 solver를 사용할 때는 책임과 쓰기 경로를 나눕니다. worktree 생성은 지침 파일만으로 자동 수행되지 않습니다. 특히 `.gitignore`로 제외한 챌린지 파일은 새 worktree에 자동 복사되지 않으므로, 원본 해시와 전달 경로를 명시합니다.

## 8. 증적과 writeup

최소 증적은 다음과 같습니다.

1. 이벤트의 규칙·범위와 문제 입력의 출처·해시.
2. 가설·근거·실험 명령·작업 디렉터리·시간.
3. 원시 stdout/stderr 또는 로그 경로와 종료 코드.
4. 결과가 가설을 지지하거나 반증하는 이유.
5. 환경과 입력에서 결과까지 이어지는 완전한 풀이 스크립트.
6. verifier의 재실행 명령·결과·형식 검사.

NOTES는 탐색 기록입니다. writeup은 확인된 풀이 경로를 1~3개의 핵심 단계로 정리하고 재현 명령을 제공합니다. 실플래그는 이벤트 내부 기록에서만 다루고, 공개 자료에서는 대회의 공유 규칙에 따라 제거합니다.

## 9. Git 공유 전 확인

`.gitignore`는 실수 가능성을 줄이지만, 이미 추적된 파일이나 `git add -f`를 막지 않습니다. 공유 전에 변경 목록과 추적 상태를 확인합니다.

```bash
git status --short
git diff --stat
git ls-files events
git check-ignore events/classroom/NOTES.md
```

템플릿을 제외한 이벤트 자료, 실플래그, 계정 토큰, 원격 접속 정보, 벤치마크 원시 실행 자료, 강사용 PPT와 렌더 산출물이 포함되지 않아야 합니다. 이미 추적됐거나 과거 커밋에 들어간 자료는 `.gitignore`를 추가해도 제거되지 않습니다. 배포 담당자는 학생에게 공개되는 이력까지 검토하고, 학생은 검토된 Git 커밋으로만 업데이트합니다.

## 10. 벤치마크 수업

### 현재 상태와 36시도 파일럿 설계

**실제 문제 풀이 결과는 아직 미측정입니다.** 러너의 검사 통과나 CLI의 응답 확인을 CTF 풀이 성과로 집계하지 않습니다. 공개 요약도 실제 데이터가 확보되기 전까지 미측정으로 유지합니다.

사용자가 확인한 설계는 **6개 합성 문제 유형 × 새 입력 2개 = 같은 12개 입력**에 다음 세 조건을 모두 적용하는 총 **36시도**입니다. 로컬 오프라인 실험 실행은 승인되었으며 외부 대상 접근과 플래그 제출은 하지 않습니다. 결과와 원시 기록은 검토가 끝날 때까지 로컬에 보관합니다.

| 조건 | 전체 작업 흐름 | 시간 예산 |
|---|---|---|
| Claude 단독 | 프로젝트 자산 없이 표준 문제·안전 지시만 받은 Claude가 풀이 | 총 240초 |
| Codex 단독 | 프로젝트 자산 없이 표준 문제·안전 지시만 받은 Codex가 풀이 | 총 240초 |
| 프로젝트 하네스 | 규칙·스킬·증적 템플릿을 적용해 Claude 풀이 → Codex 검토 → Claude 수정 | 총 240초, 단계 상한 120/60/60초 |

비교할 것은 **하네스 전체를 사용했을 때 각 단독 모델보다 얼마나 나아지는가**입니다. 같은 입력끼리 최종 정답·시간·사용량·증적·재현성을 비교합니다. 하네스의 최초 풀이, 검토, 최종 수정을 모두 보존하고 최종 산출물을 채점합니다. 규칙·스킬 제공과 두 번째 모델 검토가 함께 달라지므로 프롬프트만의 효과나 검토 모델만의 인과적 기여를 분리해 주장하지 않습니다.

하네스 세 단계가 모두 실제로 시작되면 전체는 12 + 12 + 12×3 = **60회 CLI 단계 호출**입니다. 최종 시도 36개와 구별하고, 마감시간 소진으로 프로세스가 시작되지 않은 단계는 호출에서 제외합니다. 실제 단계 수 및 풀이·검토·수정의 토큰을 시스템 비용으로 보고합니다. 총 240초를 맞춰도 호출 수·토큰이 같아지는 것은 아닙니다. 지정된 하네스 단계 외의 추가 모델·에이전트 호출은 허용하지 않습니다.

| 통제 항목 | 적용 방법 |
|---|---|
| 입력·도구·예산 | 같은 입력과 도구 환경, 같은 240초 제한 |
| 공통 요청 | 세 조건 모두 안전 범위·solve script·writeup 요구 |
| 차이 | 하네스에 저장소 자산과 Claude→Codex→Claude의 세 단계 적용 |
| 세션 | 저장소 밖의 별도 임시 루트에 새 폴더·새 세션 생성 |
| 순서 | 고정 seed로 순서를 섞고 실제 순서를 보존 |
| 분모 | 실패·타임아웃·인프라 오류를 삭제하지 않고 미실행 수도 별도 표시 |

### 자동 판정과 수동 증적 루브릭

정답은 생성 시 보관한 정답 SHA-256과 정확히 대조합니다. 정규식에 맞는 문자열이라는 이유만으로 정답 처리하지 않습니다. 재현성은 모델이 작성한 동일 스크립트를 원 입력과 새 입력에 다시 실행하여 확인하고, 풀이의 정확 일치 정답률과 각각 분리해 집계합니다. 시간은 성공 건과 전체 시도, 하네스의 개별 단계 시간을 구분합니다. 제공자별 input/output/cache token은 각 제공자의 정의에 맞춰 모든 단계를 기록하며, 미제공 값을 0으로 채우거나 구독 사용량을 임의 달러 비용으로 환산하지 않습니다.

증적의 의미적 품질은 자동 파일 수나 NOTES 길이가 아닌 **수동 채점**으로 평가합니다. [EVIDENCE-RUBRIC.md](../benchmarks/EVIDENCE-RUBRIC.md)의 네 기준을 각 0~2점, 총 8점으로 채점합니다.

| 기준 | 2점에 필요한 근거 |
|---|---|
| 실험 전 가설 | 도구 실행 전에 명확한 가설과 예상 관측을 기록 |
| 명령 재현성 | 작업 경로, 입력 식별·해시, 명령과 필요한 환경 제공 |
| 관측과 판단 | 원시 출력·종료 상태의 위치와 채택·반증 이유 연결 |
| writeup 전달성 | 입력부터 결과까지 완전한 스크립트·명령·실제 결과 연결 |

평가자는 각 점수에 로그·문서의 경로와 위치를 남깁니다. 조건 이름을 가린 사본을 독립 평가하고, 다른 평가자가 원본 근거를 대조합니다. 최초 점수, 불일치와 합의 과정을 보존합니다. 미평가 건은 0점으로 처리하지 않고 조건별 평가 완료 수와 점수 범위를 보고합니다. 내용에서 조건을 추론할 수 있으므로 완전한 블라인드라고 주장하지 않습니다.

원본 변경, 외부·다른 trial 접근, 호스트에서의 challenge 실행, 지정된 단계 외 추가 모델·백그라운드 프로세스 사용은 품질 점수와 별개의 준수 항목입니다. 확인·위반·확인불가를 기록합니다. 주요 지표는 프로토콜 유효 정답 수를 전체 관측 시도로 나눈 값이며, 기계적 플래그 일치율과 유효한 시도만의 민감도 분석도 따로 제시합니다.

### 파일럿 결과의 한계

풀이 세션의 다른 경로 접근 금지는 프롬프트 계약이며 OS 수준에서 완전히 차단한 상태가 아닙니다. 저장소 밖 새 세션은 상위 규칙 상속을 줄이지만 모든 전역 설정·스킬·hooks를 제거하지는 않습니다. `bwrap`로 네트워크와 다른 경로를 숨기는 격리는 **채점용 재실행 단계**에 적용됩니다. 실제 trace의 범위 위반은 별도 기록합니다.

6개 합성 유형의 반복 입력은 서로 상관될 수 있습니다. 따라서 36시도를 모두 독립된 실전 CTF 문제 표본으로 해석하지 않습니다. 유형 중 3개가 crypto이고 직접 단서를 주는 쉬운 과제가 있어 세 조건 모두 성공하는 천장 효과가 생길 수 있습니다. 집계기의 신뢰 구간은 이 소표본을 설명하는 수치이며, 실제 대회 분포나 어려운 원격 문제의 성능을 보장하지 않습니다. 240초 실험은 15분 전환 규칙을 검증하지 않으며, 한 가지 하네스 작업 흐름의 결과를 모든 협업 방식에 일반화하지 않습니다. 모델 업데이트·전역 설정·캐시·서비스 지연의 영향과 기록 작성·추가 호출 비용도 남습니다.

실측 방법과 실행 코드는 [benchmarks/README.md](../benchmarks/README.md)를 따릅니다. 공개 요약에 결과가 없으면 **미측정**을 표시하며 향상률을 만들지 않습니다. 실행 원본과 평가 기록은 학생 배포 저장소에 넣지 않습니다.

## 11. 실습 완료 기준

규칙이 기록되어 있고, 원본 해시가 있으며, 가설과 반증이 원시 결과에 연결되고, 다른 세션이 풀이를 재실행할 수 있으면 실습의 핵심을 완료한 것입니다. 학생 발표에서는 정답 발견보다 **어떤 증거가 어떤 판단을 바꿨는지**를 설명합니다.

상세 운영 문제는 [TROUBLESHOOTING.md](TROUBLESHOOTING.md), 설치 구조는 [BOOTSTRAP.md](BOOTSTRAP.md), 대회 질문은 [PRE-CTF-INTAKE.md](PRE-CTF-INTAKE.md)를 참고합니다.
