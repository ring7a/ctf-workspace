# CTF Workspace — Build Worklog

Reproducible record of how this workspace was assembled.
Date: 2026-10-09. Host: Windows 10. Operator: Claude Code (Fable 5.1).

## Environment at build time
| Tool | Version | Note |
|---|---|---|
| claude code | 2.1.295 | |
| codex-cli | 0.154.0 | |
| git | 2.53.0.windows.2 | |
| python | 3.11.9 (also 3.14.2 via py) | |
| docker | NOT installed | TODO before running binaries |
| WSL | not available / hangs | TODO: install WSL2 Ubuntu |

## Steps performed
1. Cloned CTF skill library `ljagiello/ctf-skills` (depth 1).
   - Pinned commit: `c332c7be1b27cb64639a20124ac55ba916adef92` (2026-09-14).
2. Vendored 11 skills into `.claude/skills/`:
   ctf-ai-ml, ctf-crypto, ctf-forensics, ctf-malware, ctf-misc, ctf-osint,
   ctf-pwn, ctf-reverse, ctf-web, ctf-writeup, solve-challenge.
   - Upstream helper scripts + README + LICENSE kept under
     `tools/vendor-ctf-skills/`.
3. Authored operating rules: `CLAUDE.md` (Claude Code) and mirrored `AGENTS.md`
   (Codex) so both tools follow identical rules.
4. Added 3 subagents in `.claude/agents/`: triager (recon), solver (one
   challenge in isolation), verifier (flag format + reproducibility check).
5. Wrote `.claude/settings.json` (tool permissions; denies reading untrusted/).
6. Added Codex MCP registration helper `tools/register-codex-mcp.ps1`.
7. Created event folder `events/2026-yeongnam/` with NOTES template, and a
   per-challenge scaffold helper `tools/new-challenge.sh`.
8. Initialized git repo and committed (vendored skills included for one-step
   reproducibility).

## Third-party / trust notes
- The ctf-skills content is third-party. Skills are instructions Claude follows;
  they were vendored at a pinned commit on the user's explicit request.
- Upstream ships a `skill_security_auditor.py` (their CI). Re-run with:
  `python tools/vendor-ctf-skills/scripts/skill_security_auditor.py` if desired.

## Open TODO before the 2026-10-14 preliminary
- [ ] Install an isolated runtime: WSL2 Ubuntu OR Docker Desktop.
- [ ] In WSL/container run: `bash tools/vendor-ctf-skills/scripts/install_ctf_tools.sh all`
- [ ] Register Codex MCP: `pwsh tools/register-codex-mcp.ps1` then `claude mcp list`.
- [ ] Read the participation agreement for AI-tool rules; fill NOTES.md rules.
- [ ] Rehearsal: run one past challenge per category through `solve-challenge`.

## How to reproduce from scratch
See `setup.ps1`. It re-clones the pinned skills and rebuilds the skills dir.
The scaffolding (CLAUDE.md, agents, settings, templates) is tracked in git.

## 2026-10-09 — Relocation
- Moved workspace from `E:\ctf` to `E:\_\Orca\Projects\ctf`.
- Updated path references in `.claude/settings.json` (CTF_WORKSPACE) and
  `tools/register-codex-mcp.ps1`. git history preserved (same repo moved).

## 2026-10-09 — WSL setup status (BLOCKED, needs reboot)
- WSL2 engine present (2.7.13, kernel 6.18); virtualization enabled;
  vmcompute running. Host-side wsl commands work (`--version`, `--shutdown`).
- Installed Ubuntu appx and registered rootfs root-only
  (`ubuntu.exe install --root`, exit 0).
- BLOCKER: every VM-starting command hangs indefinitely (>240s) and produces
  no output: `wsl -d Ubuntu ...`, `wsl -l -v`, `wsl -l -q`. Classic
  "WSL2 utility VM won't boot / needs Windows reboot" signature.
- NEXT: reboot Windows, then `wsl -d Ubuntu -u root echo WSL_OK`.
  If still hanging: `wsl --unregister Ubuntu` then reimport a rootfs tarball
  via `wsl --import` (fully unattended, avoids the Store launcher), or
  `wsl --install -d Ubuntu-24.04` (interactive user creation).
- Docker intentionally deferred (runs on WSL2 anyway; add only if a challenge
  ships a container).

## 2026-10-09 — CTF Python toolchain installed on HOST (no WSL/Docker yet)
Ran the `install_ctf_tools.sh` pip set directly on the Windows host Python 3.11
(the bash script targets apt/brew/venv on Linux; installed the PIP_PACKAGES by name).
- Installed & import-verified on host (33 of 36): pwntools 4.15, z3, sympy, gmpy2,
  py_ecc, ecdsa, pycryptodome, numpy, Pillow, capstone, unicorn, lief, yara-python,
  pefile, oletools, volatility3, scapy, ropper, ROPgadget, matplotlib, httpx, requests,
  dnspython, dnslib, segno, shodan, sqlmap, flask-unsign, frida-tools, qiling,
  uncompyle6, python-evtx, dissect.cobaltstrike.
- angr 9.2.213 → installed into separate venv `.venv-tools/` on E: (C: drive is full,
  <1GB free). Use `.venv-tools/Scripts/python.exe` for angr. unicorn-concrete disabled
  on Windows (symbolic exec OK).
- NOT installed (need MSVC C++ build tools or Linux): fpylll, hashpumpy.
  (fpylll not actually needed — CRYPTO3 solved with a hand-written pure-Python LLL.)
- pwntools limitation on host: `asm()`/shellcraft need GNU binutils `as` (absent).
  Remote exploitation, ELF/ROP parsing, packing all work. keystone is present.
- Caveat: running untrusted challenge binaries locally still prohibited (CLAUDE.md).
  Host tools cover remote pwn + static/crypto/forensic work; dynamic binary analysis
  and binutils-`as` still need WSL2/Docker. install_ctf_tools.sh `all` (apt/gdb/ghidra/
  radare2/binwalk) remains for the Linux sandbox.
- Disk note: C: was already ~full before install; purged pip cache (~610MB) to recover.

## 2026-10-09 — WSL pre-reboot checks
- `wsl --update`: no-op (engine already current).
- Pending-reboot flags (CBS, WindowsUpdate): both False.
- VM boot still hangs. Recommend Windows reboot (resets WSL2 utility VM state),
  then `wsl -d Ubuntu -u root echo WSL_OK`. If still hanging: unregister +
  reinstall (`wsl --unregister Ubuntu`; `wsl --install -d Ubuntu-24.04`,
  interactive user creation).

## 2026-10-09 (later) — Toolchain moved into project venv
Per user request, the Python toolchain is now contained in a project venv instead of host global:
- venv: `.venv-tools/` on E: — 37 packages incl pwntools, angr, z3, volatility3, qiling, etc. (import-verified).
- Host global cleaned: session-added packages uninstalled; pre-existing (numpy/Pillow/capstone/ecdsa/pycryptodome/requests/pefile/keystone) kept.
- Use `.venv-tools\Scripts\python.exe` for CTF work.
- Still absent: fpylll, hashpumpy (need MSVC); gdb/radare2/ghidra/binwalk/nc (need WSL/Docker).

## 2026-10-09 — WSL resolved + dedicated ubuntu-ctf distro
Reboot fixed the VM boot hang. Findings and actions:
- A distro already existed: `hrc-rocky` (Rocky Linux 10.1, user hanrim.choi) —
  a general dev box, NOT a CTF env (no pwntools/gdb). Left untouched; it stays
  the default distro.
- Created a DEDICATED CTF distro `ubuntu-ctf` by importing the installed Ubuntu
  appx rootfs (Ubuntu 26.04.1 LTS, install.tar.gz) via `wsl --import`
  (unattended, no interactive user prompt). VHD at %USERPROFILE%\WSL\ubuntu-ctf.
- Provisioned: user `ctf` (passwordless sudo, default user via /etc/wsl.conf),
  systemd off for fast boot.
- CTF tools: ran the vendored `install_ctf_tools.sh` (apt + python).
  - apt mode: OK.
  - python mode FAILED first time: Ubuntu 26.04 ships Python 3.14 WITHOUT
    venv/pip, so venv creation and pip both failed ("No module named pip").
  - FIX: `apt install python3-venv python3-pip python3-dev python3-full
    build-essential libgmp-dev libmpfr-dev libmpc-dev libffi-dev libssl-dev
    pkg-config`, remove the half-built venv, re-run python mode.

### Reproduce the whole distro from scratch
- `pwsh -File tools\wsl\setup-ubuntu-ctf.ps1`
  (imports ubuntu-ctf from the Ubuntu appx rootfs, then runs
  `tools\wsl\provision-ubuntu-ctf.sh` as root inside it — user, deps, tools).
- Logs kept under `docs/wsl-logs/`.
- Does not touch `hrc-rocky` or the default distro.

## 2026-10-09 — CTF Python tools: 3.14 wheel gap resolved via uv + Python 3.12
Problem: installing the pinned CTF Python packages on the distro's Python 3.14
failed widely — no cp314 wheels for numpy 2.2.6 / unicorn / lief, and angr's
pyvex fails to build on 3.14 (cffi/pycparser parse error).
Fix (now baked into provision-ubuntu-ctf.sh):
- Install `uv`, fetch standalone Python 3.12, create venv at ~/.ctf-tools/venv.
- Install packages individually (pinned, unpinned fallback). One bad pin
  (`segno==1.6.2`, nonexistent) had aborted uv's atomic resolve; individual
  mode tolerates it (segno installs unpinned).
- Two import-time fixes: `pycparser==2.22` (newer breaks `import angr`) and
  `cysignals` (needed by fpylll).
Result: 22/22 key modules import OK on Python 3.12.15 (pwn, angr, fpylll,
volatility3, unicorn, capstone, z3, sympy, gmpy2, scapy, yara, lief, oletools,
qiling, frida, ...); ROPgadget and ropper CLIs work. venv auto-activates via
~/.bashrc. Exact set frozen to tools/wsl/ctf-venv-requirements.txt (174 pkgs).
Logs: docs/wsl-logs/.

### CTF environment is now ready
- Distro `ubuntu-ctf` (Ubuntu 26.04.1 LTS), user `ctf`, enter with `wsl -d ubuntu-ctf`.
- Workspace reachable inside WSL at /mnt/e/_/Orca/Projects/ctf.
- Reproduce from scratch: `pwsh -File tools\wsl\setup-ubuntu-ctf.ps1`.
