"""The MCP server factory + its pure-Python delegation helpers.

Design rules that keep this an honest "薄外挂":

* **Thin.** Every tool is a few lines that call *existing* AlphaAgent code
  (SymbolRouter, ``data.router.classify``, ``load_config`` + ``Pipeline``,
  ``data.base.providers``) and then shape the result into plain, JSON-friendly
  Python (dict / list / str / float / None). No new business logic lives here.
* **Lazy SDK import.** The ``mcp`` library is imported *inside*
  :func:`build_server` only. Module import never requires it, so this file is
  fully testable offline (the helpers below need only the stdlib + the demo
  provider) and ``import alphaagent.mcp`` never breaks when ``mcp`` is absent.
* **Testable seams.** The serialization / delegation logic is factored into
  module-level ``_...`` helpers (``_series_to_dicts``, ``_get_prices_payload``,
  ``_classify_payload``, ``_screen_payload``, ``_list_providers_payload``). The
  registered tools are trivial wrappers around these, so tests exercise the real
  behaviour without ever importing FastMCP.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from alphaagent.core.models import PriceSeries
from alphaagent.data.base import providers
from alphaagent.data.router import SymbolRouter, classify

# Helpful message shown whenever the optional SDK is missing.
_MISSING_MCP = (
    "the 'mcp' package is required to run the AlphaAgent MCP server. "
    'Install it with:  pip install "alphaagent[mcp]"'
)


# --------------------------------------------------------------------------- #
# Pure-Python helpers (no FastMCP import; safe to unit-test offline)
# --------------------------------------------------------------------------- #
def _parse_as_of(as_of: str | None) -> date | None:
    """Turn an optional ``YYYY-MM-DD`` string into a ``date`` (or ``None``)."""

    if as_of is None or as_of == "":
        return None
    return date.fromisoformat(as_of)


def _series_to_dicts(series: PriceSeries) -> list[dict[str, Any]]:
    """Serialize a :class:`PriceSeries` into a list of OHLCV dicts.

    Oldest -> newest, matching the series order. Dates become ISO strings so the
    payload is plain JSON.
    """

    return [
        {
            "date": b.d.isoformat(),
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
        }
        for b in series.bars
    ]


def _get_prices_payload(
    router: SymbolRouter,
    symbol: str,
    *,
    as_of: str | None = None,
    lookback: int = 260,
) -> dict[str, Any]:
    """Delegate to ``router.get_prices`` and shape the result for MCP."""

    series = router.get_prices(
        symbol, as_of=_parse_as_of(as_of), lookback=int(lookback)
    )
    return {
        "symbol": series.symbol,
        "asset_type": classify(symbol).value,
        "as_of": series.as_of.isoformat() if series.as_of else None,
        "count": len(series),
        "bars": _series_to_dicts(series),
    }


def _classify_payload(symbol: str) -> dict[str, Any]:
    """Shape ``data.router.classify`` into a small dict."""

    return {"symbol": symbol, "asset_type": classify(symbol).value}


def _list_providers_payload() -> dict[str, Any]:
    """Shape the registered provider names."""

    return {"providers": providers.names()}


def _verdict_to_dict(v: Any) -> dict[str, Any]:
    """Compact a :class:`~alphaagent.core.models.Verdict` into plain Python."""

    return {
        "symbol": v.symbol,
        "rating": v.rating,
        "confidence": v.confidence,
        "key_support": list(v.key_support),
        "key_risks": list(v.key_risks),
    }


def _screen_payload(config_path: str, *, as_of: str | None = None) -> dict[str, Any]:
    """Load a config, run the pipeline, and shape a compact result dict.

    Delegates entirely to ``load_config`` + ``Pipeline.from_config().run()``.
    We keep the payload small: scored rows always, plus verdict ratings and
    entry signals only when those stages were configured/produced.
    """

    # Imported here (not at module top) purely to keep this module's import
    # surface minimal; these are all dependency-free stdlib-first modules.
    from alphaagent.core.config import load_config
    from alphaagent.core.pipeline import Pipeline

    config = load_config(config_path)
    result = Pipeline.from_config(config).run(as_of=_parse_as_of(as_of))

    scored = [
        {
            "symbol": r.symbol,
            "asset_type": r.asset_type.value,
            "score": r.score,
            "factors": dict(r.factors),
            "source_tags": list(r.source_tags),
        }
        for r in result.scored
    ]

    payload: dict[str, Any] = {
        "config_path": config_path,
        "as_of": as_of,
        "count": len(result.scored),
        "scored": scored,
    }
    if result.verdicts:
        payload["verdicts"] = [_verdict_to_dict(v) for v in result.verdicts]
    if result.signals:
        payload["signals"] = [
            {
                "symbol": s.symbol,
                "action": s.action,
                "trigger_price": s.trigger_price,
                "stop_hint": s.stop_hint,
                "rationale": s.rationale,
            }
            for s in result.signals
        ]
    return payload


def _default_router() -> SymbolRouter:
    """A router with no provider preference (uses whatever is registered).

    Tests build their own demo-pinned router; the live server uses this so real
    providers (yfinance / FMP) are picked up from the registry's fallback chain.
    """

    return SymbolRouter()


# --------------------------------------------------------------------------- #
# Server factory (this is the only place the optional SDK is imported)
# --------------------------------------------------------------------------- #
def build_server(router: SymbolRouter | None = None) -> Any:
    """Build a ``FastMCP`` server exposing AlphaAgent's data + screening tools.

    Parameters
    ----------
    router:
        Optional pre-built :class:`SymbolRouter` (handy for tests / custom
        provider preferences). Defaults to a plain router over the registry.

    Returns
    -------
    A ``mcp.server.fastmcp.FastMCP`` instance. Call ``.run()`` to serve over
    stdio.

    Raises
    ------
    ImportError
        If the optional ``mcp`` SDK is not installed, with an actionable hint.
    """

    try:
        # LAZY: the demo path and plain ``import alphaagent.mcp`` never reach here.
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on env
        raise ImportError(_MISSING_MCP) from exc

    router = router or _default_router()
    server = FastMCP("alphaagent")

    # Each tool is a thin wrapper delegating to a tested helper above. The
    # docstrings double as the tool descriptions the MCP client sees.
    @server.tool()
    def get_prices(
        symbol: str, as_of: str | None = None, lookback: int = 260
    ) -> dict[str, Any]:
        """Recent OHLCV bars for a symbol (stock or crypto), point-in-time safe.

        ``as_of`` (``YYYY-MM-DD``) bounds the data; no bar post-dates it.
        Returns ``{symbol, asset_type, as_of, count, bars:[{date,open,...}]}``.
        """

        return _get_prices_payload(
            router, symbol, as_of=as_of, lookback=lookback
        )

    @server.tool()
    def classify_symbol(symbol: str) -> dict[str, Any]:
        """Infer a symbol's asset class (equity / crypto / unknown) from its shape."""

        return _classify_payload(symbol)

    @server.tool()
    def screen(config_path: str, as_of: str | None = None) -> dict[str, Any]:
        """Run the AlphaAgent screening pipeline from a TOML config.

        Loads ``config_path``, runs pool -> filter -> (optional) agent panel ->
        (optional) entry timing, and returns a compact dict of scored rows plus
        verdict ratings / entry signals when those stages ran.
        """

        return _screen_payload(config_path, as_of=as_of)

    @server.tool()
    def list_providers() -> dict[str, Any]:
        """List the names of all registered data providers."""

        return _list_providers_payload()

    return server
