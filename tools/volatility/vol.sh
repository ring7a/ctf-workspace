#!/usr/bin/env bash
# Run Volatility 3 from the ubuntu-ctf venv with this repo's extra symbols/ and plugins/.
# usage: wsl -d ubuntu-ctf bash -lc 'bash /mnt/e/_/Orca/Projects/ctf-workspace/tools/volatility/vol.sh -f <image> <plugin> [args]'
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if command -v vol >/dev/null 2>&1; then VOL=vol
elif [[ -x "$HOME/.ctf-tools/venv/bin/vol" ]]; then VOL="$HOME/.ctf-tools/venv/bin/vol"
else echo "volatility3 not found; provision the venv (tools/wsl/) or run tools/volatility/vol.ps1 on the host" >&2; exit 1; fi
exec "$VOL" -s "$HERE/symbols" -p "$HERE/plugins" "$@"
