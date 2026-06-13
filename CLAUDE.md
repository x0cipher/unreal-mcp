# CLAUDE.md

Notes for **Claude Code** working in this repo. The full build/architecture/
contribution guide lives in **[AGENTS.md](AGENTS.md)** — read it first; this file
only adds Claude-Code-specific operational detail.

@AGENTS.md

## Environment

- **OS:** Windows 11. The default shell is **PowerShell**; a Bash tool is also
  available for POSIX one-liners. Use PowerShell syntax for Windows paths and
  native tooling (Build.bat, the venv interpreter).
- **Unreal:** UE 5.7 at `C:\Program Files\Epic Games\UE_5.7`.
- **Server venv:** `server/.venv` (Windows layout — interpreter at
  `server/.venv/Scripts/python.exe`).

## Driving the live editor from a session

The MCP server is registered with Claude Code at **user scope** (`claude mcp add
unreal-mcp …`, stored in `~/.claude.json`), so the `unreal-mcp:ping` and
`unreal-mcp:execute_python` tools are available in a fresh session **when the
Unreal Editor is open** on `MCPProject`. If the tools error with "could not reach
Unreal," the editor isn't running or the plugin didn't bind — launch it and
re-check with `ping`.

`execute_python` is the fastest way to inspect or mutate editor state while
developing — prefer it for one-off checks over rebuilding.

## Rebuild loop (important)

The editor **locks `UnrealEditor-UnrealMCP.dll`**, so a `Build.bat` rebuild needs
the editor closed first. Standard loop:

1. Close the editor (e.g. stop the `UnrealEditor` process).
2. Run the Build.bat command from [AGENTS.md](AGENTS.md#build--test).
3. Relaunch the editor; wait for port `55557`, then `ping` / `execute_python` to
   confirm.

Alternatively, Live Coding (`Ctrl+Alt+F11`) patches the running editor without a
restart — but it's user-driven from the editor UI, and a true cold start is the
better test when verifying boot-time behavior.

## House rules

- Match existing style; **AGENTS.md → Conventions** is the spec.
- Never commit build artifacts or the `reference/` clones (see `.gitignore`).
- Keep engine/UObject calls on the game thread.
