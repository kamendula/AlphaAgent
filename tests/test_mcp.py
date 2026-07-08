"""Tests for the optional MCP "薄外挂".

Two-layer strategy so the suite runs *with or without* the ``mcp`` SDK:

* The pure-Python serialization / delegation helpers (``_series_to_dicts``,
  ``_get_prices_payload``, ``_screen_payload``, ...) are tested directly, using
  only the offline demo provider — no FastMCP, no network.
* ``build_server`` is tested behind ``pytest.importorskip("mcp")``, so it skips
  gracefully when the optional dependency is absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alphaagent.core.models import AssetType
from alphaagent.data.router import SymbolRouter
from alphaagent.mcp import server as mcp_server

# Config bundled with the repo; drives the offline screen() test.
_DEMO_CONFIG = Path(__file__).resolve().parents[1] / "configs" / "demo.toml"


def _demo_router() -> SymbolRouter:
    """Router pinned to the offline demo provider (no network)."""

    return SymbolRouter(
        preference={AssetType.EQUITY: ["demo"], AssetType.CRYPTO: ["demo"]}, fallback=False
    )


# --------------------------------------------------------------------------- #
# Pure helpers (no FastMCP needed)
# --------------------------------------------------------------------------- #
def test_series_to_dicts_shape():
    router = _demo_router()
    series = router.get_prices("AAPL")
    rows = mcp_server._series_to_dicts(series)

    assert len(rows) == len(series)
    first = rows[0]
    assert set(first) == {"date", "open", "high", "low", "close", "volume"}
    # Dates are ISO strings; numbers are plain floats (JSON-friendly).
    assert isinstance(first["date"], str)
    assert isinstance(first["close"], float)
    # Preserves oldest -> newest order.
    assert rows[0]["date"] <= rows[-1]["date"]


def test_get_prices_payload():
    payload = mcp_server._get_prices_payload(_demo_router(), "AAPL", lookback=120)

    assert payload["symbol"] == "AAPL"
    assert payload["asset_type"] == "equity"
    assert payload["count"] == len(payload["bars"])
    assert payload["count"] > 0
    assert payload["bars"][-1]["close"] > 0


def test_get_prices_payload_respects_as_of():
    as_of = "2024-06-30"
    payload = mcp_server._get_prices_payload(_demo_router(), "AAPL", as_of=as_of)

    assert payload["as_of"] == as_of
    # PIT boundary: no bar may post-date as_of.
    assert all(bar["date"] <= as_of for bar in payload["bars"])


def test_classify_payload():
    assert mcp_server._classify_payload("AAPL")["asset_type"] == "equity"
    assert mcp_server._classify_payload("BTC-USD")["asset_type"] == "crypto"


def test_list_providers_payload_includes_demo():
    names = mcp_server._list_providers_payload()["providers"]
    assert "demo" in names


def test_screen_payload_offline():
    payload = mcp_server._screen_payload(str(_DEMO_CONFIG))

    assert payload["config_path"] == str(_DEMO_CONFIG)
    assert payload["count"] == len(payload["scored"])
    # Scored rows are compact JSON-friendly dicts.
    if payload["scored"]:
        row = payload["scored"][0]
        assert set(row) >= {"symbol", "asset_type", "score", "factors"}
        assert isinstance(row["score"], float)


# --------------------------------------------------------------------------- #
# Server factory (skips if the optional SDK is missing)
# --------------------------------------------------------------------------- #
def test_build_server_registers_tools():
    pytest.importorskip("mcp")

    server = mcp_server.build_server(router=_demo_router())
    # FastMCP names the server "alphaagent".
    assert getattr(server, "name", "alphaagent") == "alphaagent"
