# 트러블슈팅 — Windows + WSL + Claude Code 운영 노트

이 워크스페이스를 **Windows 10 + Git Bash(Claude Code Bash 도구) + WSL2
(`ubuntu-ctf`)** 에서 몰 때 에이전트(또는 사람)의 발목을 잡는 문제들에 대한,
어렵게 얻은 해결책. 이 리포를 공유한다면 먼저 읽으세요 — 다시 발견하는 데 실제로
시간이 많이 듭니다.

---

## 1. 두 개의 셸, 두 개의 경로 표기 — 절대 섞지 말 것
- Claude Code의 **Bash 도구는 Windows 호스트의 Git Bash(MSYS)** 다. Windows
  경로를 `C:/…` 또는 `/c/…` 로 본다. `/mnt/…` 에는 **쓸 수 없다**(그 마운트는
  WSL 안에만 존재). 바깥 출력을 `/mnt/...` 경로로 리다이렉트하면 실패한다
  (`No such file or directory`).
- **WSL** (`wsl -d ubuntu-ctf …`) 은 리포를
  `/mnt/e/_/Orca/Projects/ctf-workspace` 로, 홈 venv를 `~/.ctf-tools/venv` 로 본다.
- MSYS는 `~`, `/home/...`, `/mnt/...` 를 `wsl -- …` 의 **인자**로 넘길 때
  망가뜨린다. WSL 쪽을 `bash -lc '...'` 로 감싸고 따옴표 *안에서* `~` 를 쓰거나,
  `/mnt/...` 경로를 넘긴다. 작동하는 예:
  `wsl -d ubuntu-ctf bash -lc 'ls ~/.ctf-tools/venv'`

## 2. Bash 도구로 띄운 백그라운드 프로세스는 **죽는다** (exit 9/15)
Bash 도구를 통해 `wsl -d ubuntu-ctf bash -lc "... &"` 안에서 장시간/백그라운드
프로세스를 띄우면 **거의 즉시 SIGTERM/SIGKILL 된다**(exit 15, 이후 9). `nohup`,
`setsid`, `disown`, `</dev/null >/dev/null 2>&1` 로도 **살릴 수 없다**. WSL은 띄운
명령이 반환되면 세션의 프로세스 트리를 허물고, Bash 도구 자체의 수명 주기가 이를
가중시킨다.

**대신 살아남는 것:**
- **사용자**가 인터랙티브 프롬프트에서 `! <cmd>` 로 실행한 명령(하네스가 추적;
  포그라운드 타임아웃을 넘기면 *백그라운드로 이동*되어 계속 실행).
- **`tmux` 세션 안의 모든 것** (§3 참조). 이것이 신뢰할 수 있는, 에이전트 주도
  해결책이다.

## 3. tmux = 에이전트가 몰고 사용자가 접속할 수 있는 지속 셸
`tmux` 는 `ubuntu-ctf` 에 설치되어 있다. 분리된(detached) tmux **서버는 데몬화되어
배포판을 살려 두므로**, 세션/윈도우가 개별 Bash 도구 호출에 걸쳐 살아남는다.

```bash
# 한 번 생성 (호출에 걸쳐 유지됨):
wsl -d ubuntu-ctf bash -lc "tmux new-session -d -s ctf 'exec bash'"
# 유지됐는지 확인 (별도 호출):
wsl -d ubuntu-ctf bash -lc "tmux ls"
# 서버/도구 전용 윈도우:
wsl -d ubuntu-ctf bash -lc "tmux new-window -t ctf -n srv"
# 몰기 (명령줄 + Enter 전송):
wsl -d ubuntu-ctf bash -lc "tmux send-keys -t ctf:srv 'python3 /mnt/e/.../server.py' Enter"
# 결과 읽기 (명령이 쓰는 로그파일, 또는 pane 캡처):
wsl -d ubuntu-ctf bash -lc "tmux capture-pane -t ctf:srv -p | tail -20"
```
- **사용자가 같은 세션을 보거나 제어 가능:** `wsl -d ubuntu-ctf -- tmux attach -t ctf`
- **함정:** **포그라운드** 프로세스(예: `ssh` 터널)가 돌고 있는 pane에는 절대
  `send-keys` 하지 말 것. 키 입력은 셸이 아니라 *그 프로세스의 stdin* 으로 가서,
  당신의 "재시작"은 조용히 무효화된다. 장시간 포그라운드 프로세스마다 전용
  윈도우를 주고, 셸 명령은 다른 윈도우에서 실행한다.
- 서버 재시작: 먼저 포트를 강제로 비우지 않으면 새 프로세스가 bind에 실패하고
  **옛** 코드가 계속 서빙한다(유령 동작을 쫓게 된다). **이름이 아니라 포트로
  죽여라:** `fuser -k <port>/tcp`. 자기 명령줄에 `server.py` 가 포함된 셸에서
  `pkill -f server.py` 를 실행하면 **자기 부모 셸을 죽인다**(exit 9/SIGKILL이
  보이고 재시작은 일어나지 않음) — 이름으로 매칭해야 한다면 대괄호(`pkill -f
  '[s]erver.py'`)를 쓰고 *또한* 나머지 명령에서 그 리터럴 이름을 빼라.

## 4. **바깥** Git Bash에서 인라인 `python3` 은 불안정하다
Bash 도구에서 `python3 -c "..."` 는 엉뚱한 `Python` 배너를 내거나 non-zero로
종료하고 캡처된 출력을 오염시킬 수 있다. 인라인 헬퍼(URL 인코딩, JSON)로 쓰지
말 것. 대신: `curl -G --data-urlencode`, `jq`, 순수 bash, **또는** Python을 *WSL
안에서* 실행(`wsl -d ubuntu-ctf bash -lc 'python3 -I script.py'`). 신뢰할 수 없는
파일 분석은 무조건 WSL에서 `python -I` 로 유지한다.

## 5. 복합 WSL 명령은 빈 출력을 반환할 수 있다 (exit 9)
깊게 중첩된 `$(...)`, `echo` 에 끼워 넣은 `tmux list-windows`(그 괄호가 바깥 파싱을
깨뜨림), 긴 파이프라인은 때때로 브리지를 통해 **빈 출력 + exit 9** 로 돌아온다. 각
WSL 호출을 **단순하고 단일 목적**으로 유지하라; 체이닝 대신 결과를 파일에 쓰고
후속 호출에서 그 파일을 읽어라.

## 6. WSL 위의 pwntools: 비인터랙티브는 직접 작동, 인터랙티브는 tmux 필요
**실용적 승리(PWN1 & PWN2에서 입증):** **비인터랙티브**로 작성된 pwntools
익스플로잇은 그냥 `wsl -d ubuntu-ctf bash -lc "python3 exploit.py remote"` 로 잘
돈다 — tmux 불필요. 요령은 **전부 보낸 뒤 결과를 당기는 것**:
각 단계마다 `io.sendlineafter(prompt, payload)`, 그리고
`io.recvuntil(b'MARKER', timeout=4)` / `io.recvall(timeout=5)` 와 플래그 정규식으로
읽기. 셸을 띄운 뒤에는 `io.interactive()` 를 부르지 말고 — 대신
`io.sendline(b'cat /flag; echo DONE'); data = io.recvuntil(b'DONE', timeout=4)`.
브리지를 통해 **멈추는** 것은 진짜 인터랙티브 I/O다: `io.interactive()`, 블로킹
`recv()` 루프, `io.poll(block=True)` — 그 출력은 캡처된 stdout에 도달하지 못하는
경우가 많다. 챌린지가 정말로 왕복이 필요하면 익스플로잇을 **tmux** 윈도우에서
실행하고 `capture-pane` (§3 참조). 출력을 작게 유지하려면
`context.log_level='warning'`, 크면 파일로 리다이렉트. 신뢰할 수 없는 바이너리의
네이티브 실행은 호스트가 아니라 `ubuntu-ctf` 안에 유지. 5개 원격 서비스 모두 WSL
에서 도달 가능했으므로(`socket.create_connection`), 원격 익스플로잇은
`ubuntu-ctf` 에서 바로 실행된다.

## 7. SSRF 콜백 / 리다이렉터용 공개 터널 (계정·설치 불필요)
챌린지가 **대상이 도달할 수 있는 외부 URL**(SSRF 콜백, open-redirect/리다이렉터,
OOB 유출 싱크)을 필요로 할 때, 로컬 서버 + SSH 터널을 tmux 안에서 실행:
```bash
# 'srv' 윈도우: 8111 포트의 로컬 HTTP 서버 (콜백 또는 리다이렉트 로직)
# 'tun' 윈도우:
ssh -o StrictHostKeyChecking=accept-new -R 80:localhost:8111 nokey@localhost.run
#  -> https://<random>.lhr.life 출력  (TLS 종단, :8111 로 포워딩)
```
- 서브도메인은 **랜덤이고 재접속마다 바뀐다** — 사용 전에 ssh 출력/로그파일에서
  다시 읽어라; 페이로드에 호스트명을 고정했다면 바뀔 때 갱신하라.
- `nokey@` 로 쓰는 `localhost.run` 은 키가 필요 없다; 안정적인 서브도메인을
  원하면 SSH 키를 추가(그들의 `forever-free` 문서 참조). `serveo.net` 이 대안.

---

### 빠른 참조
| 증상 | 원인 | 해결 |
|---|---|---|
| 로그 쓸 때 `No such file or directory` | 바깥 Git Bash가 `/mnt/...` 를 못 봄 | 바깥은 `C:/...`, WSL 안은 `/mnt/...` |
| 백그라운드 프로세스 사망, exit 15/9 | Bash 도구 WSL 세션 teardown | **tmux** 안에서 실행 |
| 서버 "재시작"이 아무 일도 안 함 | send-keys가 포그라운드 ssh pane에 감 / 옛 프로세스가 포트 점유 | 윈도우 분리 + `fuser -k <port>/tcp` |
| 빈 출력, exit 9 | 복합/중첩 WSL 명령 | 호출당 단순 동작 하나, 파일에서 읽기 |
| 출력에 쓰레기 `Python` | 바깥 Git Bash의 `python3 -c` | WSL 안에서 Python 실행, 또는 `curl`/`jq` |
| pwntools `io.interactive()` 멈춤 | 브리지를 통한 인터랙티브 I/O | 비인터랙티브로 작성: `sendlineafter` + `recvuntil(MARK,timeout)`; 또는 tmux `capture-pane` |
| `pkill -f X` 에서 exit 9 / 셸 사망 | `X` 가 셸 자기 명령줄에 있음 → 자신을 죽임 | 포트로 죽이기(`fuser -k N/tcp`) 또는 대괄호(`[X]`) + 이름을 명령에서 빼기 |
| 원격 pwn 익스플로잇 | — | 바로 작동: `wsl -d ubuntu-ctf bash -lc "python3 exp.py remote"` (서비스가 WSL에서 도달 가능) |
