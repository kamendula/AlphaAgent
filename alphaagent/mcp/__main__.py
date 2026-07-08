"""Run the AlphaAgent MCP server over stdio: ``python -m alphaagent.mcp``.

Thin entry point. All imports stay lazy so that even the error path (mcp not
installed) produces a clean, actionable message instead of a traceback.
"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        # build_server imports the ``mcp`` SDK lazily and raises ImportError
        # (with an install hint) if it is missing.
        from alphaagent.mcp.server import build_server
    except ImportError as exc:  # pragma: no cover - depends on env
        print(f"alphaagent.mcp: {exc}", file=sys.stderr)
        return 1

    try:
        server = build_server()
    except ImportError as exc:  # mcp SDK absent
        print(f"alphaagent.mcp: {exc}", file=sys.stderr)
        return 1

    # FastMCP.run() defaults to the stdio transport — exactly what MCP clients
    # (Claude Code, etc.) launch as a subprocess.
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
