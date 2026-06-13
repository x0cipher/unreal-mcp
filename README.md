<div align="center">

# 🎮 UnrealMCP

### Build games by *talking* to your editor.

**UnrealMCP** plugs **Unreal Engine 5** into any LLM agent — Claude, Cursor,
Copilot — through the [Model Context Protocol](https://modelcontextprotocol.io).
Describe what you want; watch it appear in the viewport.

[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e.svg)](LICENSE)
[![Unreal Engine 5.7](https://img.shields.io/badge/Unreal%20Engine-5.7-0e1128.svg?logo=unrealengine)](https://www.unrealengine.com)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org)
[![MCP](https://img.shields.io/badge/Model%20Context%20Protocol-black.svg)](https://modelcontextprotocol.io)
[![Status: v0.1](https://img.shields.io/badge/status-v0.1%20%E2%80%94%20early-f59e0b.svg)](https://github.com/x0cipher/unreal-mcp/releases)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-8b5cf6.svg)](CONTRIBUTING.md)

</div>

---

> **You:** *"Spawn a row of glowing cubes and point a camera at them."*
>
> **Agent:** *…calls `execute_python`, runs `unreal` API, returns the captured log.*
>
> **Editor:** the cubes are there.

That's the whole idea. An agent gets a small set of MCP tools wired straight into
a running Unreal Editor, so natural language turns into real edits — actors,
assets, materials, Blueprints — with the engine's own output flowing back so the
agent can *see what it did* and fix its own mistakes.

## ✨ Why this exists

Making games is hard, and the learning curve keeps a lot of good ideas trapped in
people's heads. UnrealMCP is a bet that the gap between *"I can picture it"* and
*"it exists in the engine"* should be a conversation. It's also a great way to
learn Unreal — you can watch the agent work and read every API call it makes.

## 🧠 How it works

```
┌─────────────┐   MCP / stdio   ┌───────────────────┐   TCP :55557   ┌─────────────────────┐
│  Claude /   │ ──────────────► │  Python MCP server │ ─────────────► │  UnrealMCP plugin    │
│  Cursor /   │                 │     (server/)      │                │  (in Unreal Editor)  │
│  Copilot    │ ◄────────────── │                    │ ◄───────────── │  runs on game thread │
└─────────────┘    tool calls   └───────────────────┘   JSON cmds     └─────────────────────┘
```

- **Plugin** (`MCPProject/Plugins/UnrealMCP`) — a `UEditorSubsystem` starts a TCP
  server on `127.0.0.1:55557` from an `FRunnable` worker thread. Requests are JSON
  `{ "type": <command>, "params": {…} }`; each command is marshalled onto the
  **game thread** and answered with `{ "status": "success" | "error", … }`.
- **Server** (`server/`) — a [FastMCP](https://github.com/modelcontextprotocol/python-sdk)
  server (stdio transport) exposing MCP tools that forward to the plugin.

The headliner tool, **`execute_python`**, runs code in the editor's Python scope
(the full `unreal` module) and returns captured logs *and* any exception trace —
so the agent always knows what actually happened. It's the universal escape hatch
while native commands grow up around it.

## 🚀 Quickstart

> **Requirements:** Unreal Engine **5.7** (other 5.x likely work with minor
> tweaks), a C++ toolchain UnrealBuildTool can use (Visual Studio 2022 or VS Build
> Tools 2022 with the MSVC v143 toolchain + a Windows 10/11 SDK), **Python 3.10+**,
> and an MCP-capable client (Claude Desktop / Claude Code, Cursor, …).

**1 — Build the plugin**

```powershell
& "C:\Program Files\Epic Games\UE_5.7\Engine\Build\BatchFiles\Build.bat" `
  MCPProjectEditor Win64 Development `
  -Project="<repo>\MCPProject\MCPProject.uproject" -WaitMutex
```

Open `MCPProject/MCPProject.uproject`. The plugin auto-starts its server on load —
look for `MCP server listening on 127.0.0.1:55557` in the Output Log.

**2 — Set up the MCP server**

```bash
cd server
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
```

**3 — Connect your agent**

See [`docs/connecting-agents.md`](docs/connecting-agents.md) for Claude Desktop /
Claude Code / Cursor. Minimal Claude Desktop entry:

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

## 🕹️ Try it

With the editor open and the agent connected, ask:

> *"Use the unreal-mcp `ping` tool."* → returns `pong`.
>
> *"Spawn a cube at the origin."* → the agent calls `execute_python`:
> ```python
> import unreal
> sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
> sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, 0))
> ```

No agent handy? Run the bundled round-trip smoke test (editor open):

```bash
cd server && .venv/Scripts/python test_roundtrip.py
```

## 🗂️ Repository layout

| Path | What |
|---|---|
| `MCPProject/` | UE5 host project used to develop & test the plugin |
| `MCPProject/Plugins/UnrealMCP/` | **The plugin** — drop into any UE project to use it |
| `server/` | The Python MCP server |
| `docs/` | Connection + usage docs |

## 🗺️ Roadmap

- [x] End-to-end pipeline: `ping` + `execute_python` with log/error feedback
- [ ] Native command coverage — actors, assets, materials, Blueprints, Niagara…
- [ ] Blueprint **graph** authoring (K2Node creation + pin wiring)
- [ ] A real grounding loop — viewport screenshots + structured error feedback
- [ ] Packaging / runtime agent support

See the [Releases](https://github.com/x0cipher/unreal-mcp/releases) for what's shipped.

## 🔒 Security

UnrealMCP lets an agent **run arbitrary Python inside your editor**. The bridge
binds to loopback only and runs only while the editor is open — but there's no
auth on the local socket yet. Read [`SECURITY.md`](SECURITY.md) before you wire up
anything you don't fully trust.

## 🤝 Contributing

This is young and there's a *lot* of surface to cover — new commands, docs,
bug reports, or just trying it and telling us what broke. Start with
[`CONTRIBUTING.md`](CONTRIBUTING.md); agents and humans alike should skim
[`AGENTS.md`](AGENTS.md) for how the bridge is built.

## 📜 License

[MIT](LICENSE) © x0cipher
