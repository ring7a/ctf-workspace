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
