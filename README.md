# CTF Workspace

Claude Code + Codex workspace for CTF competitions. Skills from
[ljagiello/ctf-skills](https://github.com/ljagiello/ctf-skills) are vendored at
a pinned commit; the operating rules, subagents and templates are local.

## Layout
- `CLAUDE.md` / `AGENTS.md` — operating rules for Claude Code / Codex (identical).
- `.claude/skills/` — 11 vendored CTF skills (dispatcher: `solve-challenge`).
- `.claude/agents/` — triager, solver, verifier subagents.
- `.claude/settings.json` — tool permissions.
- `events/<event>/` — per-event NOTES.md + challenges/.
- `tools/` — helpers: `new-challenge.sh`, `register-codex-mcp.ps1`, vendored scripts.
- `docs/WORKLOG.md` — reproducible build record and TODO.
- `docs/BOOTSTRAP.md` — concept + step-by-step rebuild in a new environment.
- `tools/wsl/` — dedicated CTF Linux: `setup-ubuntu-ctf.ps1`,
  `provision-ubuntu-ctf.sh`, `ctf-venv-requirements.txt` (frozen toolchain).
- `setup.ps1` — re-installs vendored skills from the pinned commit.

## Quick start (per competition)
1. `bash tools/new-challenge.sh 2026-yeongnam <name>` for each challenge.
2. In Claude Code, let `solve-challenge` triage, or run the `triager` subagent.
3. Record every step in the challenge NOTES.md (reproducibility).
4. `verifier` subagent checks the flag; a human submits.

## Before first use
See the TODO list in `docs/WORKLOG.md` (register Codex MCP, read the AI-tool
rules, rehearse). The CTF Linux distro + toolchain is already set up here.

## Porting to another machine / another agent
This repo is self-contained and path-independent — clone it anywhere and an
agent can rebuild the whole setup. Start from `docs/BOOTSTRAP.md`: it explains
the concept and gives platform-specific rebuild steps (Windows/WSL, native
Linux, macOS, container). Challenge data is gitignored, so only the tooling and
config travel with the repo.
