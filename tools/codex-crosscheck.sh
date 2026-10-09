#!/usr/bin/env bash
# Get an independent opinion / code review from Codex (second model, different
# lineage). Codex is already logged in (ChatGPT). No MCP server needed.
#
#   tools/codex-crosscheck.sh "<question>"      # independent opinion, read-only
#   tools/codex-crosscheck.sh --review          # review uncommitted changes
#   tools/codex-crosscheck.sh --review "<focus>"# review with focus instructions
#
# Use per CLAUDE.md: when stuck past the 15-minute rule, hand Codex the current
# hypothesis AND the disproving evidence; if the two opinions diverge,
# investigate the difference before continuing.
set -euo pipefail
if [ "${1:-}" = "--review" ]; then
  shift
  exec codex review --uncommitted "${1:-Review these changes for correctness bugs and risky assumptions.}"
fi
[ $# -ge 1 ] || { echo "usage: $0 \"<question>\"  |  $0 --review [focus]" >&2; exit 2; }
exec codex exec --sandbox read-only "$*"
