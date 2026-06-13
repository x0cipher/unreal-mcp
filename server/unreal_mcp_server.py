"""UnrealMCP server.

An MCP (Model Context Protocol) server that bridges LLM agents (Claude, Cursor,
Copilot) to a running Unreal Editor. Tools are forwarded over a local TCP socket
to the UnrealMCP editor plugin, which executes them on the game thread.

Transport: stdio (the standard MCP transport for desktop agent clients).
"""

from __future__ import annotations

import base64
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


# --- Actor commands ---------------------------------------------------------
#
# These are higher-level tools templated over execute_python: each builds a small
# Python snippet, injects its arguments as a base64-encoded JSON blob (so quoting
# is never a problem), runs it in the editor, and parses a single result line
# tagged with a marker. The plugin needs no changes to add commands this way.

_RESULT_MARKER = "__MCP_RESULT__"


def _run_unreal_json(params: dict[str, Any], body: str) -> dict[str, Any]:
    """Run a Python `body` in Unreal with `params` available as `_p`.

    The body must assign a JSON-serializable value to `result`. Returns
    {"status": "success", "result": …} or {"status": "error", "error": …}.
    """
    blob = base64.b64encode(json.dumps(params).encode("utf-8")).decode("ascii")
    code = (
        "import unreal, json, base64\n"
        f'_p = json.loads(base64.b64decode("{blob}").decode("utf-8"))\n'
        f"{body}\n"
        f'unreal.log("{_RESULT_MARKER}" + json.dumps(result))\n'
    )

    resp = send_to_unreal("execute_python", {"code": code})
    if resp.get("status") != "success":
        return resp

    inner = resp.get("result", {})
    if not inner.get("success", False):
        return {
            "status": "error",
            "error": inner.get("command_result") or "Python execution failed in Unreal.",
            "log": inner.get("log"),
        }

    for line in inner.get("log", []):
        output = line.get("output", "")
        at = output.find(_RESULT_MARKER)
        if at != -1:
            payload = output[at + len(_RESULT_MARKER) :].strip()
            try:
                return {"status": "success", "result": json.loads(payload)}
            except json.JSONDecodeError:
                return {"status": "error", "error": f"Unparseable result: {payload[:300]}"}

    return {"status": "error", "error": "No result returned from Unreal.", "log": inner.get("log")}


_SPAWN_BODY = """
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
cls = getattr(unreal, _p["class_name"], None)
if cls is None:
    result = {"error": "unknown class_name: " + str(_p["class_name"])}
else:
    pitch, yaw, roll = _p["rotation"]
    actor = sub.spawn_actor_from_class(
        cls, unreal.Vector(*_p["location"]), unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw)
    )
    if actor is None:
        result = {"error": "spawn returned None"}
    else:
        sm = _p.get("static_mesh")
        if sm and hasattr(actor, "static_mesh_component"):
            mesh = unreal.EditorAssetLibrary.load_asset(sm)
            if mesh:
                actor.static_mesh_component.set_static_mesh(mesh)
        actor.set_actor_scale3d(unreal.Vector(*_p["scale"]))
        if _p.get("label"):
            actor.set_actor_label(_p["label"])
        loc = actor.get_actor_location()
        rot = actor.get_actor_rotation()
        result = {
            "label": actor.get_actor_label(),
            "class": actor.get_class().get_name(),
            "location": [round(loc.x, 2), round(loc.y, 2), round(loc.z, 2)],
            "rotation": [round(rot.pitch, 2), round(rot.yaw, 2), round(rot.roll, 2)],
            "path": actor.get_path_name(),
        }
"""


@mcp.tool()
def spawn_actor(
    class_name: str = "StaticMeshActor",
    location: list[float] | None = None,
    rotation: list[float] | None = None,
    scale: list[float] | None = None,
    label: str | None = None,
    static_mesh: str = "/Engine/BasicShapes/Cube.Cube",
) -> dict[str, Any]:
    """Spawn an actor in the current level.

    Args:
        class_name: an `unreal` actor class name, e.g. "StaticMeshActor" (default),
            "CameraActor", "PointLight", "DirectionalLight".
        location: [x, y, z] world location in cm. Default [0, 0, 0].
        rotation: [pitch, yaw, roll] in degrees. Default [0, 0, 0].
        scale: [x, y, z] scale multipliers. Default [1, 1, 1].
        label: editor display name to assign (optional).
        static_mesh: mesh asset path, used only for StaticMeshActor. Defaults to a
            unit cube. Other shapes: /Engine/BasicShapes/{Sphere,Cylinder,Cone,Plane}.

    Returns the spawned actor's label, class, location, rotation, and path.
    """
    params = {
        "class_name": class_name,
        "location": location or [0.0, 0.0, 0.0],
        "rotation": rotation or [0.0, 0.0, 0.0],
        "scale": scale or [1.0, 1.0, 1.0],
        "label": label,
        "static_mesh": static_mesh,
    }
    return _run_unreal_json(params, _SPAWN_BODY)


_LIST_BODY = """
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
flt = (_p.get("name_filter") or "").lower()
out = []
for a in sub.get_all_level_actors():
    label = a.get_actor_label()
    if flt and flt not in label.lower():
        continue
    loc = a.get_actor_location()
    out.append({
        "label": label,
        "class": a.get_class().get_name(),
        "location": [round(loc.x, 2), round(loc.y, 2), round(loc.z, 2)],
    })
result = {"count": len(out), "actors": out}
"""


@mcp.tool()
def list_actors(name_filter: str | None = None) -> dict[str, Any]:
    """List actors in the current level with their label, class, and location.

    Args:
        name_filter: optional case-insensitive substring; only actors whose label
            contains it are returned.

    Returns {"count": N, "actors": [{label, class, location}, …]}.
    """
    return _run_unreal_json({"name_filter": name_filter}, _LIST_BODY)


_SET_TRANSFORM_BODY = """
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
matches = [a for a in sub.get_all_level_actors() if a.get_actor_label() == _p["label"]]
for a in matches:
    if _p.get("location") is not None:
        a.set_actor_location(unreal.Vector(*_p["location"]), False, False)
    if _p.get("rotation") is not None:
        pitch, yaw, roll = _p["rotation"]
        a.set_actor_rotation(unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw), False)
    if _p.get("scale") is not None:
        a.set_actor_scale3d(unreal.Vector(*_p["scale"]))
result = {"matched": len(matches), "label": _p["label"]}
"""


@mcp.tool()
def set_actor_transform(
    label: str,
    location: list[float] | None = None,
    rotation: list[float] | None = None,
    scale: list[float] | None = None,
) -> dict[str, Any]:
    """Move, rotate, and/or scale the actor(s) with the given editor label.

    Only the components you pass are changed; omit an argument to leave it as-is.

    Args:
        label: the editor display name of the actor to transform.
        location: new [x, y, z] world location in cm.
        rotation: new [pitch, yaw, roll] in degrees.
        scale: new [x, y, z] scale multipliers.

    Returns {"matched": N, "label": …}. matched=0 means no actor had that label.
    """
    params = {"label": label, "location": location, "rotation": rotation, "scale": scale}
    return _run_unreal_json(params, _SET_TRANSFORM_BODY)


_DELETE_BODY = """
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
matches = [a for a in sub.get_all_level_actors() if a.get_actor_label() == _p["label"]]
for a in matches:
    sub.destroy_actor(a)
result = {"deleted": len(matches), "label": _p["label"]}
"""


@mcp.tool()
def delete_actor(label: str) -> dict[str, Any]:
    """Delete every actor with the given editor label from the current level.

    Args:
        label: the editor display name of the actor(s) to delete.

    Returns {"deleted": N, "label": …}. deleted=0 means nothing matched.
    """
    return _run_unreal_json({"label": label}, _DELETE_BODY)


if __name__ == "__main__":
    mcp.run()
