# AGENTS.md

Guidance for AI coding agents (and humans) working **in this repository**. If
you're configuring an agent to *drive Unreal at runtime*, you want
[`docs/connecting-agents.md`](docs/connecting-agents.md) instead — this file is
about contributing to the codebase.

## What this project is

UnrealMCP bridges LLM agents to a running Unreal Editor over the Model Context
Protocol. Two halves talk over a local TCP socket:

- **`MCPProject/Plugins/UnrealMCP/`** — the C++ editor plugin (the bridge).
- **`server/`** — the Python MCP server that agents connect to.

`MCPProject/` is a host UE5 project that exists only to build and test the
plugin. The plugin is the product.

## Architecture (read before touching the bridge)

```
agent ──MCP/stdio──► server/unreal_mcp_server.py ──TCP 127.0.0.1:55557──► UnrealMCP plugin ──► game thread
```

- The plugin is a `UEditorSubsystem` that spins up an `FRunnable` worker thread
  listening on `127.0.0.1:55557`.
- Wire protocol is one JSON object per connection: request
  `{ "type": <command>, "params": {…} }` → response
  `{ "status": "success" | "error", "result"|"error": … }`. The server opens a
  fresh socket per command and reads until the plugin closes it.
- **Anything that touches the editor, world, or assets must run on the game
  thread.** The bridge marshals each command onto it (via `AsyncTask` +
  `TPromise`) — don't call UObject/engine APIs from the worker thread.
- `execute_python` runs code through `IPythonScriptPlugin::ExecPythonCommandEx`
  (ExecuteFile mode, Public scope = state persists across calls, like the
  console) and returns `LogOutput` + `CommandResult`.

### Plugin source map

| File | Role |
|---|---|
| `Source/UnrealMCP/Private/UnrealMCPModule.cpp` | Module startup/shutdown |
| `Source/UnrealMCP/Private/UnrealMCPBridge.cpp` | Subsystem + command handlers (`HandlePing`, `HandleExecutePython`, dispatch) |
| `Source/UnrealMCP/Private/MCPServerRunnable.cpp` | TCP accept/read/write worker thread |
| `Source/UnrealMCP/Public/*.h` | Matching headers |

## Build & test

**Build the plugin** (the editor must be **closed** — it locks the DLL; or use
Live Coding `Ctrl+Alt+F11` from inside the editor):

```powershell
& "C:\Program Files\Epic Games\UE_5.7\Engine\Build\BatchFiles\Build.bat" `
  MCPProjectEditor Win64 Development `
  -Project="<repo>\MCPProject\MCPProject.uproject" -WaitMutex
```

**Run the server / smoke test** (editor open on `MCPProject`):

```bash
cd server
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python test_roundtrip.py     # exercises ping + execute_python
```

**Lint Python** (CI enforces this):

```bash
ruff check server && ruff format --check server
```

## Adding a command — the core workflow

A command is two small pieces. Use `ping` (trivial) and `execute_python`
(non-trivial) as templates.

1. **Plugin** — add a `HandleX(params)` method in `UnrealMCPBridge.cpp` that
   returns a result `TSharedPtr<FJsonObject>`, and route the new `type` string to
   it in the dispatch switch. Keep engine calls on the game thread (the bridge
   already gets you there). Return useful logs/errors in the result — the agent
   relies on them to self-correct.
2. **Server** — add an `@mcp.tool()` function in `server/unreal_mcp_server.py`
   that calls `send_to_unreal("<type>", {…})`. The **docstring is the tool spec
   the agent reads** — make it precise about what it does and when to use it.
3. **Rebuild → restart editor → test** via `test_roundtrip.py` or a live agent.

Favor focused native commands for common operations, but remember
`execute_python` is the always-available fallback for anything not yet wrapped.

## Conventions

- **C++** — match Unreal's style (the surrounding code is the spec): `F`/`U`/`A`
  type prefixes, `TEXT()` for string literals, UE containers (`TArray`,
  `TSharedPtr`, `FString`) over std, no raw `new`/`delete`.
- **Python** — typed, std-lib-light, `from __future__ import annotations`. Keep
  the wire protocol simple; don't add framing the plugin doesn't speak.
- **Target.cs** — keep `DefaultBuildSettings = BuildSettingsVersion.V6`. **V5
  breaks** against the prebuilt UnrealEditor (shared-build-environment mismatch).

## Environment gotchas (hard-won)

- **`.NET Framework 4.x SDK (NETFXSDK)`** is required by UnrealBuildTool
  (SwarmInterface) — the .NET 10 SDK alone is *not* enough. Install
  `Microsoft.Net.Component.4.8.SDK` + targeting pack via the VS Build Tools
  installer if the build complains about NETFXSDK.
- **Cold start:** Unreal's Python initializes lazily (~13s into boot). The first
  `execute_python` after launch could land before that. `HandleExecutePython`
  calls `ForceEnablePythonAtRuntime()` when Python isn't yet available, so the
  first call succeeds instead of erroring. Keep that fallback.
- The editor's embedded interpreter is **Python 3.11.x**, separate from whatever
  Python runs the MCP server.

## Don't

- Don't commit build artifacts (`Binaries/`, `Intermediate/`, `Saved/`,
  `DerivedDataCache/`, `.venv/`) — `.gitignore` covers these; keep it that way.
- Don't commit the `reference/` study clones — they're other projects, kept out
  of history on purpose.
- Don't call engine APIs off the game thread.
