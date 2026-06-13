"""Live smoke test for the actor command tools (no MCP client required).

Imports the server module and calls the actor tools directly, so it exercises
the real tool code (arg injection + result parsing), then verifies the editor
state. Run with the Unreal Editor open on MCPProject (the plugin auto-starts).

    .venv/Scripts/python test_actors.py        # Windows
    .venv/bin/python test_actors.py            # macOS/Linux

Exit code 0 = all steps passed.
"""

from __future__ import annotations

import sys
import time

import unreal_mcp_server as s

LABEL = "MCP_SmokeTest"


def _result(resp: dict) -> dict:
    """Unwrap a tool response, raising with context if it errored."""
    if resp.get("status") != "success":
        raise AssertionError(f"tool error: {resp.get('error')}")
    return resp["result"]


def wait_for_editor(max_wait: float = 120.0) -> bool:
    print(f"Waiting for Unreal bridge on {s.UNREAL_HOST}:{s.UNREAL_PORT}...")
    start = time.time()
    while time.time() - start < max_wait:
        if s.ping().get("status") == "success":
            print(f"  bridge is up after {time.time() - start:.0f}s")
            return True
        time.sleep(3.0)
    return False


def main() -> int:
    if not wait_for_editor():
        print("FAILED: bridge never came up. Is the editor open on MCPProject?")
        return 1

    # Start clean in case a previous run left the actor behind.
    s.delete_actor(LABEL)

    print("\n[1/5] spawn_actor (cube @ 0,0,100)")
    spawned = _result(s.spawn_actor(label=LABEL, location=[0, 0, 100]))
    print("  ->", spawned)
    assert spawned.get("label") == LABEL, "spawn did not apply the label"

    print("\n[2/5] list_actors (filtered)")
    listed = _result(s.list_actors(name_filter=LABEL))
    print("  ->", listed)
    assert listed["count"] == 1, f"expected 1 actor, got {listed['count']}"

    print("\n[3/5] set_actor_transform (move + scale)")
    moved = _result(s.set_actor_transform(LABEL, location=[250, 100, 0], scale=[2, 2, 2]))
    print("  ->", moved)
    assert moved["matched"] == 1, "transform matched no actor"

    print("\n[4/5] verify the move landed")
    after = _result(s.list_actors(name_filter=LABEL))["actors"][0]
    print("  ->", after)
    assert after["location"] == [250.0, 100.0, 0.0], f"location wrong: {after['location']}"

    print("\n[5/5] delete_actor + verify gone")
    deleted = _result(s.delete_actor(LABEL))
    print("  ->", deleted)
    assert deleted["deleted"] == 1, "delete removed nothing"
    assert _result(s.list_actors(name_filter=LABEL))["count"] == 0, "actor still present"

    print("\nRESULT: PASS - all actor tools work end to end!")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(f"\nRESULT: FAIL - {exc}")
        sys.exit(1)
