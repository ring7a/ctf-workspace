# CTF Workspace — Claude Code Operating Rules

You are the analysis partner for a CTF team. Scope of action is limited to
challenge files the competition provides and the servers the competition
explicitly designates. Never touch scoreboard infrastructure, other teams,
or any host not listed in the active event's NOTES.md.

## Workflow (enforced every challenge)
1. Recon first: identify file type, strings, protections, category.
2. Form exactly ONE hypothesis before running any exploit tooling.
3. Test it with the smallest possible experiment.
4. Record result in the challenge's NOTES.md (fact / disproof / next step).
5. Next hypothesis. Never spray tools without a hypothesis.

## 15-minute rule
If an approach shows no progress in ~15 minutes, switch approaches and write
the switch reason in NOTES.md. Do not tunnel.

## Skills
- Start unknown challenges with the `solve-challenge` skill (dispatcher/recon).
- It routes to `ctf-web`, `ctf-pwn`, `ctf-crypto`, `ctf-reverse`,
  `ctf-forensics`, `ctf-malware`, `ctf-osint`, `ctf-misc`, `ctf-ai-ml`.
- Use `ctf-writeup` after solving to capture a reproducible writeup.

## Environment
- Host: Windows 10. Analysis of untrusted binaries/files MUST run inside the
  isolated WSL distro `ubuntu-ctf` (Ubuntu 26.04 LTS), never on the host.
  Enter with `wsl -d ubuntu-ctf`; CTF tools live in the auto-activated venv
  ~/.ctf-tools/venv. The workspace is at /mnt/e/_/Orca/Projects/ctf-workspace inside WSL.
  (Docker 29.1 is installed and its daemon runs in ubuntu-ctf; use it when a challenge ships a container.)
- Keep original challenge files in `<challenge>/untrusted/`. Do all work in
  `<challenge>/work/`. Pass paths as arguments; never run an interpreter from
  inside the untrusted directory. Run analysis Python with `python -I`.

## Reporting format
Every status update is three lines:
- Hypothesis: ...
- Confirmed facts: ...
- Next experiment: ...

## Pre-CTF intake (do this first, every event)
At the start of an event, before touching any challenge, run the intake in
`docs/PRE-CTF-INTAKE.md`: ask the user those questions (grouped, concise) and
write the answers into `events/<event>/NOTES.md`. Do NOT start solving until the
blocking items are known: AI-tool rules, flag format, in/out-of-scope targets.

## Flag handling
- Read the active event's NOTES.md for the flag format and submission rules.
- The verifier agent checks flag format; a human submits. No auto-submission.

## Collaboration with Codex
Codex is a second model (different lineage) that is already logged in. Use it
for an independent opinion or code review via the shell (no MCP server needed):
- Second opinion: `tools/codex-crosscheck.sh "<hypothesis + disproving evidence>"`
  (wraps `codex exec --sandbox read-only`).
- Code review of a solve script / exploit: `tools/codex-crosscheck.sh --review`
  (wraps `codex review --uncommitted`).
When stuck past the 15-minute rule, hand Codex the current hypothesis AND the
disproving evidence. If the two opinions diverge, investigate the difference
before continuing. AGENTS.md mirrors this file so Codex follows identical rules.
