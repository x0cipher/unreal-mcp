# Security Policy

## The one thing you must understand

UnrealMCP gives an LLM agent the ability to **execute arbitrary Python inside
your Unreal Editor**. That Python has the full power of the `unreal` module and
the host machine's Python runtime — it can read and write files, spawn
processes, and modify or delete your project's assets.

Treat the bridge like an open shell on your machine, because that is
effectively what it is.

### How we limit blast radius

- The plugin's TCP server **binds to `127.0.0.1` only** (loopback). It is not
  reachable from other machines on your network by default.
- It only runs while the **Unreal Editor is open** with the plugin enabled.
- There is **no authentication** on the local socket (v0.1). Any process on
  your machine that can open `127.0.0.1:55557` can drive the editor.

### Your responsibilities

- Only connect agents and MCP clients you trust.
- Don't run UnrealMCP on a shared/multi-user machine where you don't control
  every local process.
- Don't expose port `55557` beyond loopback (no port-forwarding, no `0.0.0.0`
  binds, no reverse proxies).
- Review what your agent is about to run when the stakes are high. The
  `execute_python` tool returns captured logs and errors so you can see what
  happened.

## Supported versions

This project is pre-1.0. Security fixes land on `main`; there are no backports.

| Version | Supported |
|---------|-----------|
| `main`  | ✅        |
| < 0.1   | ❌        |

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Use GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
("Report a vulnerability" under the repo's **Security** tab). I'll acknowledge
within a few days and work with you on a fix and disclosure timeline.

When reporting, include: what you found, how to reproduce it, and the impact you
think it has.
