#!/usr/bin/env bash
# Usage: bash tools/new-challenge.sh <event> <challenge-name>
set -euo pipefail
EVENT="${1:?event}"; NAME="${2:?challenge name}"
BASE="events/$EVENT/challenges/$NAME"
mkdir -p "$BASE/untrusted" "$BASE/work"
cat > "$BASE/NOTES.md" <<INNER
# $NAME

## Given
- files: (put originals in untrusted/)
- remote:

## Category / protections

## Hypotheses log
- [ ] H1:
      test:
      result:

## Commands run (reproducible)
\`\`\`bash
\`\`\`

## Flag
INNER
echo "Created $BASE"
