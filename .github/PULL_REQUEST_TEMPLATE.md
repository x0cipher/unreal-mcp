<!-- Thanks for contributing to UnrealMCP! Keep PRs focused. -->

## What & why

<!-- What does this change, and what problem does it solve? -->

## How I tested it

<!-- e.g. rebuilt the plugin, ran server/test_roundtrip.py, drove it from an agent.
     Paste relevant Output Log lines or the execute_python `log` field if useful. -->

## Checklist

- [ ] Engine/UObject calls stay on the game thread
- [ ] Python passes `ruff check server` and `ruff format --check server`
- [ ] New command? Added both the plugin handler **and** the server `@mcp.tool()` with a clear docstring
- [ ] Commits follow [Conventional Commits](https://www.conventionalcommits.org) (release-please generates the changelog from them)
- [ ] No build artifacts or `reference/` clones committed
