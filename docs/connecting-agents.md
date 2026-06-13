# Connecting agents to UnrealMCP

The MCP server (`server/unreal_mcp_server.py`) speaks MCP over **stdio**, so any
stdio-capable MCP client can use it. In every case you point the client at the
venv Python and the server script.

Replace `<repo>` with the absolute path to this repository
(e.g. `C:/Users/arkak/projects/mcp/unreal`). On Windows, use the
`.venv/Scripts/python.exe` interpreter so the `mcp` package is on the path.

## Claude Desktop

Edit `claude_desktop_config.json`
(Windows: `%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "unreal-mcp": {
      "command": "<repo>/server/.venv/Scripts/python.exe",
      "args": ["<repo>/server/unreal_mcp_server.py"]
    }
  }
}
```

Restart Claude Desktop. The unreal-mcp tools (`ping`, `execute_python`,
`spawn_actor`, `list_actors`, `set_actor_transform`, `delete_actor`) should appear.

## Claude Code (CLI)

```bash
claude mcp add unreal-mcp -- "<repo>/server/.venv/Scripts/python.exe" "<repo>/server/unreal_mcp_server.py"
```

Or add the same `mcpServers` block to your project's `.mcp.json`.

## Cursor

Add to `.cursor/mcp.json` (project) or the global Cursor MCP settings:

```json
{
  "mcpServers": {
    "unreal-mcp": {
      "command": "<repo>/server/.venv/Scripts/python.exe",
      "args": ["<repo>/server/unreal_mcp_server.py"]
    }
  }
}
```

## Sanity check (no agent needed)

You can exercise the server's transport with the MCP CLI dev inspector:

```bash
cd server
.venv/Scripts/python -m mcp dev unreal_mcp_server.py
```

…or hit the Unreal plugin directly over TCP to confirm the editor side is up
(Unreal Editor must be running with the plugin enabled):

```bash
python - <<'PY'
import socket, json
s = socket.create_connection(("127.0.0.1", 55557), timeout=5)
s.sendall(json.dumps({"type": "ping", "params": {}}).encode())
print(s.recv(65536).decode())
PY
```

Expect: `{"status":"success","result":{"success":true,"message":"pong"}}`

## Troubleshooting

- **"Could not reach Unreal on 127.0.0.1:55557"** — the Unreal Editor isn't
  running, the plugin isn't enabled, or it failed to bind. Check the editor
  Output Log for `MCP server listening on 127.0.0.1:55557`.
- **`execute_python` says Python is not available** — enable the *Python Editor
  Script Plugin* in the project (it's listed as a dependency of UnrealMCP, so it
  should be on by default).
- **Tools don't appear in the client** — verify the `command` path points at the
  venv `python.exe` and the script path is absolute.
