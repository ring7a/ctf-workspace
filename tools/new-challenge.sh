#!/usr/bin/env bash
# Usage: bash tools/new-challenge.sh <event> <challenge-name>
set -euo pipefail
die() { printf '%s\n' "$*" >&2; exit 2; }
[ "$#" -eq 2 ] || die "Usage: bash $0 <event> <challenge-name>"
EVENT="$1"; NAME="$2"
for part in "$EVENT" "$NAME"; do
  [[ "$part" =~ ^[[:alnum:]][[:alnum:]_.-]*$ ]] || die "Use a name starting with a letter/number and containing only letters, numbers, _, . or -."
done
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
BASE="$ROOT/events/$EVENT/challenges/$NAME"
# Refuse links at every writable path component, including dangling links.
# Run this helper only in a workspace whose directories you control.
for dir in "$ROOT/events" "$ROOT/events/$EVENT" "$ROOT/events/$EVENT/challenges"; do
  [ ! -L "$dir" ] || die "Refusing symlink: $dir"
  if [ -e "$dir" ]; then
    [ -d "$dir" ] || die "Not a directory: $dir"
  else
    mkdir -- "$dir"
  fi
done
[ ! -e "$BASE" ] && [ ! -L "$BASE" ] || die "Challenge already exists; preserving all evidence: $BASE"
mkdir -- "$BASE"
mkdir -- "$BASE/untrusted" "$BASE/work"
set -o noclobber
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
