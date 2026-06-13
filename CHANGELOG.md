# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once it reaches 1.0.

## [Unreleased]

### Added
- Open-source project scaffolding: license, contributing guide, code of conduct,
  security policy, agent guides (`AGENTS.md`, `CLAUDE.md`), issue/PR templates,
  and CI.

## [0.1.0] - 2026-06-13

The first end-to-end proof that the pipeline works.

### Added
- **UnrealMCP editor plugin** — a `UEditorSubsystem` that starts a TCP server on
  `127.0.0.1:55557` from an `FRunnable` worker thread, marshalling each command
  onto the game thread.
- **`ping`** command — health check; returns `pong`.
- **`execute_python`** command — runs Python in the editor's shared scope via
  `ExecPythonCommandEx` (ExecuteFile mode, Public scope) and returns captured log
  output plus any exception trace, so the agent can see what actually happened.
- **Python MCP server** (`server/`) — a FastMCP (stdio) server exposing `ping`
  and `execute_python` as MCP tools that forward to the plugin.
- **Cold-start fallback** — `execute_python` calls `ForceEnablePythonAtRuntime()`
  when Python hasn't lazily initialized yet, so the first call right after editor
  boot succeeds instead of failing.
- Round-trip smoke test (`server/test_roundtrip.py`) and connection docs
  (`docs/connecting-agents.md`).

[Unreleased]: https://github.com/x0cipher/UnrealMCP/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/x0cipher/UnrealMCP/releases/tag/v0.1.0
