"""Optional MCP (Model Context Protocol) wrapper — a thin "薄外挂".

This package exposes AlphaAgent's data + screening to MCP clients (e.g. Claude
Code), so the project can ride the MCP ecosystem without any of its own logic
moving out of the main package. It is strictly *optional*:

* Nothing on the demo path imports it. The default ``make demo`` / CLI flow
  never touches this module, so the dependency-free promise is intact.
* The ``mcp`` SDK is a soft dependency, imported **lazily** inside
  :func:`build_server` (never at module top level). If it is absent, importing
  this package still works — you only hit a clear, actionable error when you
  actually try to build/run the server.

Install the extra and run it over stdio::

    pip install "alphaagent[mcp]"
    python -m alphaagent.mcp

The single public entry point is :func:`build_server`, a factory that returns a
configured ``FastMCP`` instance with a small tool surface (get_prices,
classify_symbol, screen, list_providers). All tools delegate to existing
AlphaAgent code — this layer only serializes to plain JSON-friendly Python.
"""

from __future__ import annotations

# NB: we import the *factory* by name here, not the ``mcp`` SDK. server.py keeps
# the FastMCP import lazy, so ``import alphaagent.mcp`` stays cheap and safe even
# without the optional dependency installed.
from alphaagent.mcp.server import build_server

__all__ = ["build_server"]
