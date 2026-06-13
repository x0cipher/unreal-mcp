"""End-to-end smoke test for the UnrealMCP bridge (no MCP client required).

Connects directly to the plugin's TCP server, waits for the editor to come up,
then exercises `ping` and `execute_python`. Run with the Unreal Editor open on
the MCPProject (the plugin starts its server automatically).

    python test_roundtrip.py
"""

from __future__ import annotations

import json
import socket
import sys
import time

HOST = "127.0.0.1"
PORT = 55557


def send(command: str, params: dict | None = None, timeout: float = 30.0) -> dict:
    payload = json.dumps({"type": command, "params": params or {}}).encode("utf-8")
    with socket.create_connection((HOST, PORT), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(payload)
        chunks = []
        while True:
            data = sock.recv(65536)
            if not data:
                break
            chunks.append(data)
    return json.loads(b"".join(chunks).decode("utf-8").strip())


def wait_for_editor(max_wait: float = 600.0) -> bool:
    print(f"Waiting for Unreal bridge on {HOST}:{PORT} (up to {max_wait:.0f}s)...")
    start = time.time()
    while time.time() - start < max_wait:
        try:
            resp = send("ping", timeout=5.0)
            if resp.get("status") == "success":
                print(f"  bridge is up after {time.time() - start:.0f}s -> {resp}")
                return True
        except (ConnectionRefusedError, OSError):
            pass
        time.sleep(3.0)
    return False


def main() -> int:
    if not wait_for_editor():
        print("FAILED: bridge never came up. Is the editor loading the MCPProject?")
        return 1

    print("\n[1/2] ping")
    print("  ->", send("ping"))

    print("\n[2/2] execute_python: spawn a cube at the origin and report actor count")
    code = (
        "import unreal\n"
        "actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)\n"
        "cube = unreal.EditorAssetLibrary.load_asset('/Engine/BasicShapes/Cube.Cube')\n"
        "loc = unreal.Vector(0.0, 0.0, 0.0)\n"
        "sma = actor_sub.spawn_actor_from_class(unreal.StaticMeshActor, loc)\n"
        "sma.static_mesh_component.set_static_mesh(cube)\n"
        "sma.set_actor_label('MCP_HelloCube')\n"
        "all_actors = actor_sub.get_all_level_actors()\n"
        "unreal.log('MCP spawned cube; level now has %d actors' % len(all_actors))\n"
        "print('spawned:', sma.get_actor_label())\n"
    )
    resp = send("execute_python", {"code": code})
    print("  ->", json.dumps(resp, indent=2))

    ok = resp.get("status") == "success" and resp.get("result", {}).get("success")
    print("\nRESULT:", "PASS - cube spawned, round trip works!" if ok else "see output above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
