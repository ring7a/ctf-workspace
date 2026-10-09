# Registers Codex as an MCP server inside Claude Code (project scope).
# Run from the workspace root (E:\_\Orca\Projects\ctf).
# Lets Claude ask Codex for a second opinion mid-session.
claude mcp add codex --scope project -- codex mcp-server
Write-Host "Registered. Verify with: claude mcp list"
