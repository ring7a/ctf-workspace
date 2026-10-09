# Pre-CTF Intake — questions the AI must get answered before solving

At the start of any event, before touching challenges, the agent asks the user
these and records the answers in `events/<event>/NOTES.md`. Do not start
solving until the **blocking** items (marked [!]) are answered — proceeding
without them risks rule violations or wasted work.

## Rules & authorization  [!]
1. Does the participation agreement ALLOW AI tools? Any limits (e.g. no
   automated scanning, no external/cloud services, must be human-submitted)?
2. Flag format and exact regex? (e.g. `FLAG{...}`, `MARINE{...}`)
3. Scoreboard URL and how to submit. Wrong-flag penalty or lockout?
4. In-scope targets (hosts/CIDRs/URLs) — what MAY we touch?
5. Out-of-scope / forbidden (scoreboard, other teams, infra, the platform
   itself, DoS, brute force)? Rate limits on challenge servers?

## Access & logistics
6. Event window: start, end, timezone.
7. How do we get challenge files (download link, attachments, per-challenge)?
8. Network: VPN/proxy required? Offline segment for the final?
9. Team: members, who owns which categories, shared account or individual?
10. Any rule on sharing writeups or tooling during/after the event?

## Working agreements
11. Who submits flags (default: a human submits after `verifier` checks format)?
12. Where to record progress (default: per-challenge NOTES.md + event NOTES.md)?
13. Priorities — categories we're strongest/weakest in, target score?

The agent should ask these concisely (group them), accept "unknown / N/A",
and write the answers into the event NOTES.md "Rules" section before work
begins. Re-ask the blocking items if the event rules change mid-competition.
