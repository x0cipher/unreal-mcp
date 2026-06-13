# Contributing to UnrealMCP

Thanks for being here. UnrealMCP is young and there's a lot of surface to cover,
so contributions of every size are welcome — a new command, a doc fix, a bug
report, or just trying it and telling us what broke.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to help

- **Add a command** — wire up a new capability (actors, assets, materials,
  Blueprints, Niagara…). See [Adding a command](#adding-a-command) below.
- **Improve grounding** — screenshots, structured error feedback, anything that
  helps an agent see what it just did.
- **Docs & examples** — quickstarts, recipes, agent prompts that work well.
- **Report bugs** — open an issue with repro steps. The editor Output Log and the
  `log` field returned by `execute_python` are gold here.

## Project layout

| Path | What |
|---|---|
| `MCPProject/` | UE5 host project used to develop & test the plugin |
| `MCPProject/Plugins/UnrealMCP/` | **The plugin** — drop into any UE project |
| `server/` | The Python MCP server (FastMCP, stdio) |
| `docs/` | Connection + usage docs |

Architecture lives in [`AGENTS.md`](AGENTS.md) — read it before touching the
bridge; it explains the thread model and wire protocol.

## Dev setup

You'll need the same things listed in the [README requirements](README.md#requirements):
Unreal Engine 5.7, a C++ toolchain UnrealBuildTool can use, and Python 3.10+.

**Build the plugin:**

```powershell
& "C:\Program Files\Epic Games\UE_5.7\Engine\Build\BatchFiles\Build.bat" `
  MCPProjectEditor Win64 Development `
  -Project="<repo>\MCPProject\MCPProject.uproject" -WaitMutex
```

The DLL is locked while the editor is open, so close the editor before a
rebuild (or use Live Coding: `Ctrl+Alt+F11`).

**Set up the server:**

```bash
cd server
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
```

**Smoke-test the round trip** (editor open on `MCPProject`):

```bash
.venv/Scripts/python test_roundtrip.py
```

## Adding a command

A command is two small pieces — a handler in the plugin and a tool in the
server. Use `ping` as the minimal template.

1. **Plugin side** (`MCPProject/Plugins/UnrealMCP/Source/UnrealMCP/`): add a
   handler that takes a `params` JSON object and returns a result object. Make
   sure anything touching the editor/world runs on the **game thread** (the
   bridge already marshals commands there) and route the new `type` to it.
2. **Server side** (`server/unreal_mcp_server.py`): add an `@mcp.tool()` function
   that calls `send_to_unreal("<your_command>", {...})`. Give it a clear
   docstring — the agent reads it to decide when to call the tool.
3. **Rebuild** the plugin, restart the editor, and exercise it from
   `test_roundtrip.py` or a connected agent.

Prefer adding focused native commands over asking agents to hand-write Python for
common operations — but `execute_python` is always the escape hatch for anything
not yet covered.

## Code style

- **C++** — follow Unreal's conventions (the surrounding code is the spec): type
  prefixes (`F`/`U`/`A`), `TEXT()` for literals, no raw `new`/`delete` where a UE
  container or smart pointer fits.
- **Python** — keep it std-lib-light and typed. CI runs
  [`ruff`](https://docs.astral.sh/ruff/); format and lint before pushing:
  ```bash
  ruff check server && ruff format --check server
  ```

## Pull requests

- Branch off `main`, keep PRs focused, and describe what you changed and how you
  tested it.
- Write [Conventional Commit](https://www.conventionalcommits.org) messages
  (`feat:`, `fix:`, `docs:`, `refactor:`, …). Releases and the changelog are
  generated automatically from these via [release-please](https://github.com/googleapis/release-please),
  so there's no changelog to update by hand — your commit subject *is* the
  release note.
- Be patient and kind in review — same goes for us.

Not sure where to start or whether an idea fits? Open an issue and ask. No
question is too small.
