"""UnrealMCP server.

An MCP (Model Context Protocol) server that bridges LLM agents (Claude, Cursor,
Copilot) to a running Unreal Editor. Tools are forwarded over a local TCP socket
to the UnrealMCP editor plugin, which executes them on the game thread.

Transport: stdio (the standard MCP transport for desktop agent clients).
"""

from __future__ import annotations

import json
import logging
import socket
from typing import Any

from mcp.server.fastmcp import FastMCP

# --- Configuration ----------------------------------------------------------

UNREAL_HOST = "127.0.0.1"
UNREAL_PORT = 55557
CONNECT_TIMEOUT = 10.0
RECV_TIMEOUT = 60.0
RECV_CHUNK = 65536

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("unreal-mcp")

mcp = FastMCP("unreal-mcp")


# --- Unreal connection ------------------------------------------------------


def send_to_unreal(command: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Open a connection to the Unreal plugin, send one command, return the parsed response.

    One command per connection keeps the wire protocol trivial: we send a single
    JSON object and read until the plugin closes the socket.
    """
    payload = json.dumps({"type": command, "params": params or {}}).encode("utf-8")

    try:
        with socket.create_connection((UNREAL_HOST, UNREAL_PORT), timeout=CONNECT_TIMEOUT) as sock:
            sock.settimeout(RECV_TIMEOUT)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.sendall(payload)

            chunks: list[bytes] = []
            while True:
                data = sock.recv(RECV_CHUNK)
                if not data:
                    break
                chunks.append(data)
    except (ConnectionRefusedError, OSError) as exc:
        return {
            "status": "error",
            "error": (
                f"Could not reach Unreal on {UNREAL_HOST}:{UNREAL_PORT} ({exc}). "
                "Is the Unreal Editor open with the UnrealMCP plugin enabled?"
            ),
        }

    raw = b"".join(chunks).decode("utf-8", errors="replace").strip()
    if not raw:
        return {"status": "error", "error": "Empty response from Unreal."}

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"status": "error", "error": f"Invalid JSON from Unreal: {raw[:500]}"}


# --- Tools ------------------------------------------------------------------


@mcp.tool()
def ping() -> dict[str, Any]:
    """Check that the Unreal Editor bridge is reachable. Returns 'pong' on success."""
    return send_to_unreal("ping")


@mcp.tool()
def execute_python(code: str) -> dict[str, Any]:
    """Execute Python code inside the running Unreal Editor and return its output.

    The code runs in the editor's shared Python scope (state persists between
    calls, like the Python console). The full `unreal` module is available, so
    this is the most general way to drive the editor — spawn actors, edit assets,
    inspect the level, etc.

    Captured `print()` / log output is returned in the `log` field, and any
    exception trace is returned in `command_result` with success=false.

    Example:
        execute_python(code="import unreal; unreal.log('hello from Unreal')")
    """
    return send_to_unreal("execute_python", {"code": code})


if __name__ == "__main__":
    mcp.run()
