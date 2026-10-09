# BOOTSTRAP — rebuild this CTF workspace in a new environment

Audience: a Claude Code (or Codex) agent setting this workspace up on a fresh
machine. Read this top to bottom, then execute the steps for your platform.
Everything here is reproducible from the files already in this repo.

## Concept (what this workspace is)

A portable CTF competition workspace with four layers:

1. **Knowledge layer — vendored skills.** `.claude/skills/` holds 11 CTF skills
   from `ljagiello/ctf-skills`, pinned at a commit. `solve-challenge` is the
   dispatcher: it triages a challenge and routes to the category skill
   (`ctf-web`, `ctf-pwn`, `ctf-crypto`, `ctf-reverse`, `ctf-forensics`,
   `ctf-malware`, `ctf-osint`, `ctf-misc`, `ctf-ai-ml`), plus `ctf-writeup`.
2. **Rules layer.** `CLAUDE.md` (Claude Code) and the identical `AGENTS.md`
   (Codex) define the operating loop: recon -> one hypothesis -> minimal test
   -> record in NOTES.md -> next; a 15-minute switch rule; flag handling;
   the Claude+Codex cross-check protocol.
3. **Automation layer — subagents.** `.claude/agents/`: `triager` (recon/sort,
   read-only), `solver` (one challenge end-to-end in an isolated worktree),
   `verifier` (flag format + reproducibility, read-only).
4. **Runtime layer — isolated Linux.** Untrusted challenge binaries run only
   inside a dedicated Linux environment with the CTF toolchain, never on the
   host. The exact package set is frozen in
   `tools/wsl/ctf-venv-requirements.txt`.

Design principles: keep the main session context clean (delegate to
subagents + worktrees); make every solve reproducible (commands go in the
challenge NOTES.md); separate concerns (dedicated CTF Linux, never the host
dev box); vendor + pin skills so the environment is deterministic.

## What is version-controlled vs not

- Tracked: skills, rules, agents, settings, tools/scripts, docs, event NOTES
  templates. This is the whole setup — enough to rebuild.
- Ignored (`.gitignore`): `events/*/challenges/` entirely (challenge data and
  solve work are per-event, untrusted, and often large/binary).

## Rebuild steps

### 0. Get the repo
Clone it (or copy the folder). All paths below are relative to the repo root;
nothing depends on where you put it.

### 1. Skills (any platform)
Skills are already vendored under `.claude/skills/`. To refresh from the pinned
upstream commit: `pwsh -File setup.ps1` (Windows) — or on Linux/mac, clone
`ljagiello/ctf-skills` at the commit in
`tools/vendor-ctf-skills/PINNED_COMMIT.txt` and copy its `ctf-*` and
`solve-challenge` folders into `.claude/skills/`.
Open Claude Code from the repo root so it auto-discovers `.claude/`.

### 2. Isolated CTF Linux + toolchain

**Windows + WSL2** (what this repo was built on):
- `pwsh -File tools\wsl\setup-ubuntu-ctf.ps1`
  Imports a dedicated `ubuntu-ctf` distro and provisions it
  (`tools\wsl\provision-ubuntu-ctf.sh`): user `ctf`, apt analysis tools, and a
  Python 3.12 venv (via `uv`) installed from the frozen requirements.
- Enter with `wsl -d ubuntu-ctf`; the CTF venv auto-activates.

**Native Linux / macOS / a container:** you don't need the `.ps1`. Reproduce
the toolchain directly:
```bash
# system tools (Debian/Ubuntu example)
bash tools/vendor-ctf-skills/scripts/install_ctf_tools.sh apt
# python toolchain — use Python 3.12 (NOT 3.13/3.14: missing wheels, angr build fails)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
uv venv --python 3.12 ~/.ctf-tools/venv
VIRTUAL_ENV=~/.ctf-tools/venv uv pip install -r tools/wsl/ctf-venv-requirements.txt
echo '[ -f ~/.ctf-tools/venv/bin/activate ] && source ~/.ctf-tools/venv/bin/activate' >> ~/.bashrc
```
On RPM distros use the installer's other modes; the Python part is identical.

### 3. Codex collaboration (optional but recommended)
Register Codex as an MCP server so Claude can get a second opinion:
`pwsh -File tools\register-codex-mcp.ps1` (or `claude mcp add codex --scope
project -- codex mcp-server`). Keep `AGENTS.md` == `CLAUDE.md`.

### 4. Per competition
- Fill `events/<event>/NOTES.md` with the flag format/regex, server scope, and
  the AI-tool rules from the participation agreement.
- `bash tools/new-challenge.sh <event> <name>` scaffolds each challenge
  (`untrusted/` for originals, `work/` for your work, a NOTES.md).

## Hard-won gotchas (don't rediscover these)
- **Python 3.14 breaks the toolchain**: no cp314 wheels for several pins, and
  angr's pyvex won't build. Use **Python 3.12**.
- **angr import error** (`CLexer ... no setter`): pin `pycparser==2.22`.
- **fpylll import error** (`No module named cysignals`): `pip install cysignals`.
- **uv resolves atomically**: one bad pin (e.g. a nonexistent version) aborts
  the whole install. Install per-package with a fallback, or use the frozen
  requirements which are known-good.
- **Git on Windows adds CRLF**: strip `\r` from shell scripts before running
  them inside Linux (`sed -i 's/\r$//' script.sh`).

## Full history
`docs/WORKLOG.md` has the dated, blow-by-blow record and the raw logs are under
`docs/wsl-logs/`.
