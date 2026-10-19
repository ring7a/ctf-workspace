# 이 저장소에서 스킬 예제를 적용하는 방법

`.claude/skills/`가 관리 원본이고 `.agents/skills/`는 동일 내용의 Codex 노출본이다.
참조 문서는 upstream 기법 사전이며, 실행 전 현재 이벤트의 `NOTES.md`와 루트의
`CLAUDE.md`/`AGENTS.md` 운영 규칙을 적용한다.

- 이벤트 인테이크의 AI 사용·플래그 형식·대상 범위가 확인된 뒤 풀이를 시작한다.
- 새로운 대상은 첫 능동 요청 전에 이벤트 NOTES에 연관성과 주소를 기록한다.
- 예제 명령은 자동 실행 목록이 아니다. 가설 하나와 최소 실험에 맞는 부분만 쓴다.
- 원본은 `<challenge>/untrusted/`, 명령 실행과 산출물은 `<challenge>/work/`로
  분리한다. 신뢰할 수 없는 파일 분석과 실행은 전용 Linux 안에서 하고 분석용
  Python 명령에는 `-I`를 붙인다. 참고 예제의 상대 경로는 실제 파일 인자로 바꾼다.
- `ctf-pwn/scripts/`는 주소·offset·입출력 규약을 채워야 하는 예제다. 성공 보장
  도구가 아니다. `ctf-web/scripts/async_fuzz.py`의 고급 처리·속도 조절도 대상에
  사용하기 전 작은 로컬 예제로 검증한다.
- 도구 설치는 문제 풀이의 측정 시간 밖에서 준비한다. 기본 툴체인은
  `tools/wsl/`을 사용한다. upstream installer는 저장소 루트 기준
  `tools/vendor-ctf-skills/scripts/install_ctf_tools.sh`에 있다.
- 명령·입출력 증거·실패·다음 가설을 challenge NOTES에 기록한다. 산출물의 경로와
  SHA-256, 도구/모델 버전, 실행 시각·종료 코드가 있으면 재현 확인이 쉬워진다.
- 후보 플래그는 verifier가 실제 입력에서 재실행하고 형식을 검사한다. 제출은
  사람이 수행하며, 에이전트가 CTFd 제출 API를 호출하지 않는다.
- `writeup.md`는 private challenge 디렉터리에 쓴다. 공개 발표/수업용 복사본에는
  실제 플래그·토큰·이벤트 전용 인프라를 싣지 않고 재배포 규칙을 따른다.

스킬은 독립된 보안 경계가 아니다. WSL의 호스트 마운트·Windows interop·네트워크,
Docker 권한, 모델 CLI의 실제 권한을 별도로 확인한다. 운영 규칙의 문장만으로
호스트 접근이나 범위 밖 요청이 기술적으로 차단되었다고 주장하지 않는다.

로컬 수정: 11개 스킬에 이 안내 연결; Codex 형식 검사와 호환되도록 compatibility
설명을 YAML 밖 본문으로 이동; installer 경로 수정; CTFd 자동 제출 예제
제거; writeup의 private 출력 위치 명시. upstream 원문 MIT 고지는
`tools/vendor-ctf-skills/LICENSE`에 보존한다. 변경 후
`python -I tools/check-workspace.py --sync`로 미러와 해시를 갱신한다.
