# Troubleshooting — Windows + WSL + Claude Code operating notes

Hard-won fixes for issues that slow down an agent (or a person) driving this
workspace from **Windows 10 + Git Bash (the Claude Code Bash tool) + WSL2
(`ubuntu-ctf`)**. If you share this repo, read this first — these cost real time
to rediscover.

---

## 1. Two shells, two path styles — never mix them
- The Claude Code **Bash tool is Git Bash (MSYS)** on the Windows host. It sees
  Windows paths as `C:/…` or `/c/…`. It **cannot** write to `/mnt/…` (that mount
  only exists inside WSL). Redirecting outer output to a `/mnt/...` path fails
  (`No such file or directory`).
- **WSL** (`wsl -d ubuntu-ctf …`) sees the repo at `/mnt/e/_/Orca/Projects/ctf-workspace`
  and the home venv at `~/.ctf-tools/venv`.
- MSYS mangles `~`, `/home/...`, `/mnt/...` when passed as **arguments** to
  `wsl -- …`. Wrap the WSL side in `bash -lc '...'` and use `~` *inside* the quotes,
  or pass a `/mnt/...` path. Example that works:
  `wsl -d ubuntu-ctf bash -lc 'ls ~/.ctf-tools/venv'`

## 2. Background processes launched via the Bash tool get **killed** (exit 9/15)
Launching a long-running/background process inside `wsl -d ubuntu-ctf bash -lc "... &"`
through the Bash tool gets **SIGTERM/SIGKILL'd almost immediately** (exit 15, then 9).
`nohup`, `setsid`, `disown`, `</dev/null >/dev/null 2>&1` do **not** save it. WSL tears
down the session's process tree when the launching command returns, and the Bash
tool's own lifecycle compounds it.

**What persists instead:**
- A command the **user** runs from the interactive prompt with `! <cmd>` (it is
  tracked by the harness; when it exceeds the foreground timeout it is *moved to the
  background* and keeps running).
- **Anything inside a `tmux` session** (see §3). This is the reliable, agent-driven fix.

## 3. tmux = persistent shell the agent drives and the user can attach
`tmux` is installed in `ubuntu-ctf`. A detached tmux **server daemonizes and keeps the
distro alive**, so sessions/windows survive across separate Bash-tool calls.

```bash
# create once (survives across calls):
wsl -d ubuntu-ctf bash -lc "tmux new-session -d -s ctf 'exec bash'"
# verify it persisted (separate call):
wsl -d ubuntu-ctf bash -lc "tmux ls"
# a dedicated window for a server/tool:
wsl -d ubuntu-ctf bash -lc "tmux new-window -t ctf -n srv"
# drive it (send a command line + Enter):
wsl -d ubuntu-ctf bash -lc "tmux send-keys -t ctf:srv 'python3 /mnt/e/.../server.py' Enter"
# read what it did (via a logfile the command writes, or capture the pane):
wsl -d ubuntu-ctf bash -lc "tmux capture-pane -t ctf:srv -p | tail -20"
```
- **The user can watch/control the same session:** `wsl -d ubuntu-ctf -- tmux attach -t ctf`
- **Pitfall:** never `send-keys` to a window whose pane is running a **foreground**
  process (e.g. an `ssh` tunnel). The keystrokes go to *that process's stdin*, not a
  shell — your "restart" silently no-ops. Give each long-running foreground process
  its own window, and run shell commands in a different one.
- Restarting a server: force-free the port first or the new process fails to bind and
  the **old** code keeps serving (you'll chase ghost behaviour). **Kill by port, not by
  name:** `fuser -k <port>/tcp`. `pkill -f server.py` run from a shell whose own command
  line contains `server.py` **kills its own parent shell** (you'll see exit 9/SIGKILL and
  the restart never happens) — if you must match by name, use a bracket (`pkill -f
  '[s]erver.py'`) *and* keep the literal name out of the rest of that command.

## 4. `python3` inline in the **outer** Git Bash is unreliable
`python3 -c "..."` from the Bash tool can emit stray `Python` banners / exit non-zero
and corrupt captured output. Don't use it for inline helpers (URL-encoding, JSON).
Instead: use `curl -G --data-urlencode`, `jq`, pure-bash, **or** run Python *inside WSL*
(`wsl -d ubuntu-ctf bash -lc 'python3 -I script.py'`). Keep untrusted-file analysis in
WSL with `python -I` regardless.

## 5. Compound WSL commands can return empty output (exit 9)
Deeply nested `$(...)`, `tmux list-windows` interpolated into an `echo` (its parens
break the outer parse), and long pipelines sometimes come back **empty with exit 9**
through the bridge. Keep each WSL invocation **simple and single-purpose**; write
results to a file and read the file in a follow-up call rather than chaining.

## 6. pwntools over WSL: non-interactive works directly; interactive needs tmux
**The practical win (proved on PWN1 & PWN2):** a pwntools exploit written
**non-interactively** runs fine with a plain `wsl -d ubuntu-ctf bash -lc "python3
exploit.py remote"` — no tmux needed. The trick is to **send everything, then pull the
result**: `io.sendlineafter(prompt, payload)` for each step, and read with
`io.recvuntil(b'MARKER', timeout=4)` / `io.recvall(timeout=5)` and a regex for the flag.
After popping a shell, don't call `io.interactive()` — instead
`io.sendline(b'cat /flag; echo DONE'); data = io.recvuntil(b'DONE', timeout=4)`.
What **hangs** through the bridge is truly interactive I/O: `io.interactive()`, blocking
`recv()` loops, `io.poll(block=True)` — their output often never reaches captured stdout.
If a challenge genuinely needs back-and-forth, run the exploit inside a **tmux** window
and `capture-pane` (see §3). Set `context.log_level='warning'` to keep output small, and
redirect to a file if it's large. Native execution of untrusted binaries stays inside
`ubuntu-ctf`, never the host. All 5 remote services were reachable from WSL
(`socket.create_connection`), so remote exploits run straight from `ubuntu-ctf`.

## 7. Public tunnel for SSRF callbacks / redirectors (no account, no install)
When a challenge needs an **external URL the target can reach** (SSRF callback, an
open-redirect/redirector, an OOB exfil sink), run a local server + an SSH tunnel inside
tmux:
```bash
# in window 'srv': a local HTTP server on 8111 (callback or redirect logic)
# in window 'tun':
ssh -o StrictHostKeyChecking=accept-new -R 80:localhost:8111 nokey@localhost.run
#  -> prints https://<random>.lhr.life  (TLS-terminated, forwards to :8111)
```
- The subdomain is **random and rotates on every reconnect** — re-read it from the
  ssh output/logfile before each use; if you pin a hostname in your payload, update it
  when it changes.
- `localhost.run` with `nokey@` needs no key; add your SSH key for a stable subdomain
  (see their `forever-free` docs). `serveo.net` is an alternative.

---

### Quick reference
| Symptom | Cause | Fix |
|---|---|---|
| `No such file or directory` writing a log | outer Git Bash can't see `/mnt/...` | use a `C:/...` path outside, `/mnt/...` inside WSL |
| background proc dies, exit 15/9 | Bash-tool WSL session teardown | launch it inside **tmux** |
| "restart" of a server does nothing | send-keys hit a foreground ssh pane / old proc holds the port | separate window + `fuser -k <port>/tcp` |
| empty output, exit 9 | compound/nested WSL command | one simple action per call, read from a file |
| garbage `Python` in output | `python3 -c` in outer Git Bash | run Python inside WSL, or use `curl`/`jq` |
| pwntools `io.interactive()` hangs | interactive I/O through the bridge | write it non-interactive: `sendlineafter` + `recvuntil(MARK,timeout)`; or tmux `capture-pane` |
| exit 9 / shell dies on `pkill -f X` | `X` is in the shell's own command line → kills itself | kill by port (`fuser -k N/tcp`) or bracket (`[X]`) + keep name out of the command |
| remote pwn exploit | — | works directly: `wsl -d ubuntu-ctf bash -lc "python3 exp.py remote"` (services reachable from WSL) |
