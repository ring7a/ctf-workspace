#!/usr/bin/env bash
# Run the pinned, local REA CLI/MCP in ubuntu-ctf. Arguments remain literal.
set -euo pipefail

fail() { printf '%s\n' "REA: $*" >&2; exit 1; }
[[ "$(uname -s)" == Linux && -r /proc/sys/kernel/osrelease ]] || fail 'Run inside WSL ubuntu-ctf.'
grep -qi microsoft /proc/sys/kernel/osrelease || fail 'Run inside WSL ubuntu-ctf.'
[[ "${WSL_DISTRO_NAME:-}" == ubuntu-ctf ]] || fail 'Use the isolated ubuntu-ctf distribution.'
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
BASE="$ROOT/.integrations/rea"
PROJECT_KEY="$(printf '%s' "$ROOT" | sha256sum | cut -c1-16)"
NATIVE_BASE="$HOME/.ctf-integrations/rea/$PROJECT_KEY"
RUNTIME="$NATIVE_BASE/work/runtime"
for dir in "$ROOT/.integrations" "$BASE" "$BASE/work" "$HOME/.ctf-integrations" "$HOME/.ctf-integrations/rea" \
  "$NATIVE_BASE" "$NATIVE_BASE/work" "$RUNTIME" "$RUNTIME/node" "$RUNTIME/app"; do
  [[ ! -L "$dir" ]] || fail "Refusing symlink runtime directory: $dir"
done
[[ -d "$RUNTIME" ]] || fail 'Install first: bash tools/integrations/install-rea.sh'
[[ "$(realpath -- "$RUNTIME")" == "$RUNTIME" ]] || fail 'Runtime path escapes the workspace.'
NODE="$RUNTIME/node/bin/node"
ENTRY="$RUNTIME/app/node_modules/rea-agents/scripts/rea.mjs"
[[ -x "$NODE" && -f "$ENTRY" ]] || fail 'Incomplete installation; rerun install-rea.sh.'
for executable in "$NODE" "$ENTRY"; do
  [[ "$(realpath -- "$executable")" == "$RUNTIME/"* ]] || fail 'Executable path escapes the runtime.'
done
export GHIDRA_INSTALL_DIR="${GHIDRA_INSTALL_DIR:-$RUNTIME/ghidra/ghidra_12.1.4_PUBLIC}"
export JAVA_HOME="${JAVA_HOME:-$RUNTIME/jdk}"
export REA_ANALYSIS_PROVIDER="${REA_ANALYSIS_PROVIDER:-ghidra}"
export REA_GHIDRA_STARTUP_TIMEOUT_MS="${REA_GHIDRA_STARTUP_TIMEOUT_MS:-330000}"
export GHIDRA_HEADLESS_MAXMEM="${GHIDRA_HEADLESS_MAXMEM:-2G}"
export PATH="$RUNTIME/node/bin:$JAVA_HOME/bin:$PATH"
# Do not redirect protocol stdout or copy the user's credentials into runtime state.
# Ghidra owns an ephemeral project; explicit CLI outputs stay in the caller's work.
cd -- "$BASE/work"
exec "$NODE" "$ENTRY" "$@"
