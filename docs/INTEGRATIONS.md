# REA/Ghidra 통합

REA는 Ghidra 분석을 CLI와 MCP 도구로 제공한다. 프로젝트의 정찰·가설·최소 실험·
증거 기록·독립 검증 흐름에서 사용하며 플래그는 사람이 제출한다.

## 현재 단말 상태 — 2026-10-14

Windows 관리자 실행으로 `WslService`를 복구해 현재 `Running` 상태이며
`ubuntu-ctf` VM이 부팅된다. 새 사용자 `.wslconfig`에 메모리 3GB·프로세서 2개를
설정했다. 기존 파일은 없었다. REA 6.4.0·Node 24.15.0·Temurin JDK 21.0.11+10·
Ghidra 12.1.4를 설치했고 scoped doctor가 정상이다. 프로젝트 MCP 등록과 실제 MCP
초기화·170개 도구 목록과 합성 바이너리의 Ghidra 개요·의사 코드 분석을 확인했다.
Evidence 내보내기·snapshot 사본 해시·바이너리 닫기·Java 프로세스 정리까지 검증했다.
결과는 [상태 기록](INTEGRATION-STATUS-2026-10-14.md)에 있다.

## 설치와 연결

전용 WSL을 [설치 안내](BOOTSTRAP.md)에 따라 준비한 뒤 저장소 루트에서 실행한다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/setup-integrations.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tools/setup-integrations.ps1 -Check
```

setup의 설치 대상은 REA 하나다. `-Component rea`를 명시할 수 있으며 기존 명령의
`-Component all`도 REA만 설치한다. `ExecutionPolicy Bypass`는 해당 자식 프로세스의
검토된 로컬 스크립트 실행에만 적용하며 전역 실행 정책이나 관리자 권한을 바꾸지 않는다.

실제 다운로드·설치·분석은 `ubuntu-ctf`에서 수행하며 기존 CTF venv는 유지한다.
Node·JDK·Ghidra·REA runtime은 Linux 파일 시스템의
`~/.ctf-integrations/rea/<workspace-key>/work/runtime/`에 설치한다. `<workspace-key>`는
저장소 POSIX 절대 경로 SHA-256의 앞 16자리이므로 저장소마다 runtime을 분리한다.
Windows 드라이브 위에서 발생하는 Linux 심볼릭 링크 생성 실패를 피하기 위한 경로다.
저장소 `.integrations/rea/untrusted/`에는 다운로드 캐시를, `.integrations/rea/work/logs/`와
`install-state.json`에는 진단·설치 기록을 남긴다. [검토 버전](../tools/integrations/reviewed-versions.json)은 REA 6.4.0,
Node 24.15.0, Temurin JDK 21.0.11+10, Ghidra 12.1.4다. 설치기는 공식 다운로드의
해시를 확인하고 npm SRI·release commit·의존성 lock을 설치 기록에 남긴다.

REA scoped doctor가 통과하면 프로젝트 `.mcp.json`과 `.codex/config.toml`에 WSL stdio
연결을 등록한다. 기존 서버·모델 설정은 보존하고 다른 `rea` 등록과 충돌하면 중단한다.
인증정보를 복사하지 않는다. Claude/Codex를 다시 열어 새 MCP 도구를 발견한다.
등록만 다시 수행하려면 `-RegisterOnly`를 사용한다.

MCP startup 제한은 90초, 도구 호출 제한은 420초, Ghidra cold startup 제한은 330초다.
처음 바이너리를 분석할 때에는 기존 벤치마크의 60초 검토 단계와 다른 시간 조건이다.

## 사용과 증거 기록

```powershell
wsl -d ubuntu-ctf -- bash tools/rea.sh doctor --provider ghidra --json
wsl -d ubuntu-ctf -- bash tools/rea.sh --help
```

[ctf-reverse REA 참조](../.claude/skills/ctf-reverse/rea.md)를 따른다. 원본은 challenge의
`untrusted/`에 두고 Evidence·분석 프로젝트·로그는 `work/`에 둔다. 정확히 가설 하나를
세우고 필요한 도구만 호출하며 `normalized_result`, `evidence_id`, 오류·partial 상태를
기록한다. `close_binary` 전에 Evidence를 내보내고 cleanup 결과도 기록한다.
REA 출력과 디컴파일 결과는 검토할 데이터다. exit 0만으로 완전한 분석이나 정답을 확정하지 않는다.

이 단말의 Windows 마운트에서는 `export_evidence_bundle`의 보호된 파일 출력이
`execution_failure/write/io`로 실패했다. 엄격한 파일 권한을 사용하는 Evidence bundle과
snapshot은 Linux native 경로 `~/.ctf-integrations/rea/<workspace-key>/work/` 아래의
별도 challenge 작업 디렉터리에서 생성한다. 디렉터리 권한은 0700으로 설정하고 생성된 파일의
바이트·SHA-256을 확인한 뒤 challenge `work/`에 보존용 사본을 둔다. 원본 입력은 계속
challenge `untrusted/`에서 읽으며 분석은 `ubuntu-ctf` 안에서 수행한다.
Windows 마운트 자체의 권한 정책을 변경하는 방법은 이 설치에서 검증하지 않았다.

REA는 분석 도구다. 기존 로그인된 Claude/Codex가 MCP를 호출하므로 별도의 모델 JSON bridge나
API 키를 설치할 필요가 없다. 호스트에서는 챌린지 바이너리를 실행하지 않는다.

## WSL 서비스 복구

WSL 서비스가 종료 대기에 멈춘 경우에만 다음 읽기 전용 진단을 사용한다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/repair-wsl-service.ps1
```

진단이 복구 대상임을 확인한 뒤 관리자 PowerShell에서 `-Apply`를 사용한다.
`-InstallAfter`를 함께 쓰면 서비스 복구 후 REA 설치를 이어간다. 복구기는 서비스 PID·상태와
VM/WSL host 프로세스 부재를 재확인하고 조건이 다르면 중단한다. 정상 실행 중인 VM을 종료하는
명령으로 사용하지 않는다.

## 학생 배포와 측정

학생 Git에는 REA 설치기·실행기·운영 참조·검토 버전을 포함한다. runtime·node_modules·
Ghidra/JDK 바이너리·로그·플래그·자격증명·단말별 MCP 설정·PPT는 제외하며 각 단말에서 설치한다.

2026-10-12의 48회 벤치마크는 당시 구성의 결과다. REA를 추가했다고 이전 결과를 성능 향상
증거로 재해석하지 않는다. 새 도구의 효과를 측정할 때에는 별도 실험 조건과 결과를 기록한다.

출처: [REA 설치](https://github.com/morluto/rea/blob/main/docs/installation.md),
[Evidence 계약](https://github.com/morluto/rea/blob/main/docs/mcp-contracts.md),
[REA 라이선스 고지](https://github.com/morluto/rea/blob/main/THIRD_PARTY_NOTICES.md),
[Codex MCP 설정](https://developers.openai.com/codex/mcp/).

# Volatility 3 통합 (메모리 포렌식) — 2026-10-18

메모리 이미지는 **Volatility 3 먼저** 가 운영 규칙이다(`CLAUDE.md`/`AGENTS.md` 스킬 절). 통합은 MCP가
아니라 **래퍼 + 저장소 자산**이다. Volatility는 Python CLI라 Claude/Codex가 셸로 직접 호출하고 출력을
읽는 편이 MCP보다 단순하고, 심볼·플러그인을 Git으로 함께 배포할 수 있다.

- 실행: `tools/volatility/vol.ps1`(호스트, 포터블 `volatility3-win-exes-*` — `$env:CTF_VOL_EXE` 또는
  `tools/volatility/bin/vol.exe`, gitignore) / `tools/volatility/vol.sh`(ubuntu-ctf venv의 volatility3 2.27.0).
  두 래퍼 모두 `-s tools/volatility/symbols -p tools/volatility/plugins`를 자동 전달한다.
- 자산: `symbols/linux/*.json.xz`(자체 생성 ISF, 표는 `symbols/README.md`), `plugins/keyring.py`
  (커널 키링 순회 → LUKS2 볼륨키), `scripts/`(vmdk→/boot 추출, vmlinuz→ELF→BTF→ISF, ISF 보정, LUKS2 오프라인 복호).
  호스트 보조 의존성은 `scripts/requirements-host.txt`, ubuntu-ctf는 `tools/wsl/ctf-venv-requirements.txt`에 dissect 패키지를 추가했다.
- 절차·판단: [ctf-forensics/memory-volatility.md](../.claude/skills/ctf-forensics/memory-volatility.md), 도구 설명 [tools/volatility/README.md](../tools/volatility/README.md).
- 호스트 실행 범위: 메모리 덤프 읽기와 플러그인 실행만. `--dump`로 꺼낸 바이너리는 챌린지 `work/` 전용
  폴더에 두고 호스트에서 실행·열람하지 않는다(필요하면 ubuntu-ctf).
