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
