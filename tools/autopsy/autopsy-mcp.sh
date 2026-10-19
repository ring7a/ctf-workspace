#!/usr/bin/env bash
# Probe the Autopsy MCP server (autopsy-mcp-stdio) outside Claude: confirm it runs,
# whether a case is open, and (optionally) list its tools / case summary.
# The MCP is a READ-ONLY query interface to a case the examiner has open in the Autopsy GUI.
#
# usage (Git Bash on the Windows host):
#   bash tools/autopsy/autopsy-mcp.sh                # get_server_status (default)
#   bash tools/autopsy/autopsy-mcp.sh tools          # tools/list
#   bash tools/autopsy/autopsy-mcp.sh summary         # get_case_summary
#   bash tools/autopsy/autopsy-mcp.sh datasources     # query_data_sources
#   bash tools/autopsy/autopsy-mcp.sh call <toolName> '<json-args>'   # arbitrary tool
#
# Override the binary with:  CTF_AUTOPSY_MCP=/c/path/to/autopsy-mcp-stdio.exe
set -euo pipefail

EXE="${CTF_AUTOPSY_MCP:-}"
if [[ -z "$EXE" ]]; then
  # newest Autopsy-*/bin/autopsy-mcp-stdio.exe under Program Files
  EXE="$(ls -1d "/c/Program Files/Autopsy-"*/bin/autopsy-mcp-stdio.exe 2>/dev/null | sort -V | tail -1 || true)"
fi
[[ -x "$EXE" ]] || { echo "autopsy-mcp-stdio not found; set CTF_AUTOPSY_MCP=/c/.../autopsy-mcp-stdio.exe" >&2; exit 1; }

cmd="${1:-status}"
case "$cmd" in
  status)      method="get_server_status"; args='{}';;
  tools)       method="__tools_list__";    args='{}';;
  summary)     method="get_case_summary";  args='{}';;
  datasources) method="query_data_sources"; args='{}';;
  call)        method="${2:?tool name}";   args="${3:-{}}";;
  *)           method="$cmd";              args="${2:-{}}";;   # treat arg1 as a tool name
esac

# MCP stdio handshake: initialize -> initialized -> (tools/list | tools/call)
{
  printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"ctf-probe","version":"1.0"}}}'
  sleep 0.6
  printf '%s\n' '{"jsonrpc":"2.0","method":"notifications/initialized"}'
  sleep 0.4
  if [[ "$method" == "__tools_list__" ]]; then
    printf '%s\n' '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
  else
    printf '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"%s","arguments":%s}}\n' "$method" "$args"
  fi
  sleep 2
} | timeout 30 "$EXE" 2>/dev/null | grep '"id":2' | tail -1
