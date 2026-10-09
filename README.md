# CTF Workspace

A reproducible, portable workspace for running CTF competitions with Claude Code
and Codex. It bundles a vetted skill library, shared operating rules, review-ready
subagents, and a one-command isolated Linux toolchain — so any machine, or any
agent, can rebuild the exact same setup from scratch.

**What's inside**
- **11 CTF skills** (web, pwn, crypto, reverse, forensics, malware, osint, misc,
  ai-ml, writeup) vendored from
  [ljagiello/ctf-skills](https://github.com/ljagiello/ctf-skills) at a pinned
  commit; `solve-challenge` triages a challenge and routes to the right one.
- **Shared rules** for Claude Code (`CLAUDE.md`) and Codex (`AGENTS.md`): a
  hypothesis-driven solve loop, a 15-minute switch rule, a pre-CTF intake, flag
  handling, and Claude↔Codex cross-checking.
- **Subagents** (`.claude/agents/`): `triager`, `solver`, `verifier`.
- **A dedicated Linux toolchain** (Ubuntu + a Python 3.12 venv with pwntools,
  angr, volatility3, and more) reproducible from `tools/wsl/` and a frozen
  requirements file.

Per-event challenge data and flags are **never tracked** — only the tooling and
config travel with the repo. New here? Start with `docs/BOOTSTRAP.md`.

## Layout
- `CLAUDE.md` / `AGENTS.md` — operating rules for Claude Code / Codex (identical).
- `.claude/skills/` — 11 vendored CTF skills (dispatcher: `solve-challenge`).
- `.claude/agents/` — `triager`, `solver`, `verifier` subagents.
- `.claude/settings.json` — tool permissions.
- `events/` — `_TEMPLATE/` only; per-event folders are gitignored.
- `tools/` — `new-challenge.sh`, `codex-crosscheck.sh`, `wsl/`, vendored scripts.
- `tools/wsl/` — dedicated CTF Linux: `setup-ubuntu-ctf.ps1`,
  `provision-ubuntu-ctf.sh`, `ctf-venv-requirements.txt` (frozen toolchain).
- `docs/BOOTSTRAP.md` — concept + step-by-step rebuild in a new environment.
- `docs/WORKLOG.md` — dated build record. `docs/PRE-CTF-INTAKE.md` — event-start questions.
- `setup.ps1` — re-installs the vendored skills from the pinned commit.

## Quick start (per competition)
1. Copy `events/_TEMPLATE/` to `events/<event>/` and fill `NOTES.md` via
   `docs/PRE-CTF-INTAKE.md` (AI-tool rules, flag format, scope).
2. `bash tools/new-challenge.sh <event> <name>` to scaffold each challenge.
3. Let `solve-challenge` triage, or run the `triager` subagent; record every
   step in the challenge NOTES.md.
4. `verifier` checks the flag; a human submits. Stuck? `tools/codex-crosscheck.sh`
   gets an independent read from Codex.

## Porting to another machine / another agent
This repo is self-contained and path-independent — clone it anywhere and an
agent can rebuild the whole setup. `docs/BOOTSTRAP.md` explains the concept and
gives platform-specific rebuild steps (Windows/WSL, native Linux, macOS,
container). Challenge data is gitignored, so only the tooling and config travel
with the repo.
