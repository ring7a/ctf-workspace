# CTF Workspace — Codex Operating Rules (mirror of CLAUDE.md)

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
- Host: Windows 10. Analysis of untrusted binaries/files MUST run inside an
  isolated environment (WSL2 Ubuntu or a Docker container), never on the host.
  (NOTE: as of setup, neither WSL nor Docker is installed — install one before
  running or executing challenge binaries. See docs/WORKLOG.md TODO.)
- Keep original challenge files in `<challenge>/untrusted/`. Do all work in
  `<challenge>/work/`. Pass paths as arguments; never run an interpreter from
  inside the untrusted directory. Run analysis Python with `python -I`.

## Reporting format
Every status update is three lines:
- Hypothesis: ...
- Confirmed facts: ...
- Next experiment: ...

## Flag handling
- Read the active event's NOTES.md for the flag format and submission rules.
- The verifier agent checks flag format; a human submits. No auto-submission.

## Collaboration with Codex
When stuck past the 15-minute rule, hand the current hypothesis and the
disproving evidence to Codex for an independent opinion. If the two opinions
diverge, investigate the difference before continuing. AGENTS.md mirrors this
file so Codex follows identical rules.
