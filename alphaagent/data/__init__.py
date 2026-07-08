"""Data layer: a provider abstraction + symbol routing.

Agents and filters never name a data source directly. They ask the router for a
symbol, the router classifies it and dispatches to a registered
:class:`~alphaagent.data.base.DataProvider`, falling back down a chain on
failure. Adding a source is one file under ``providers/`` + one ``@register``.
"""

from alphaagent.data.base import DataProvider, providers
from alphaagent.data.router import SymbolRouter

# Import built-in providers for their registration side effects.
from alphaagent.data.providers import demo as _demo  # noqa: F401
from alphaagent.data.providers import yfinance_provider as _yf  # noqa: F401

# FMP (Financial Modeling Prep) — live source, needs FMP_API_KEY at runtime.
# Registered here for discovery; it stays inert (and the demo path dependency-
# free) until a config actually routes a symbol to it.
from alphaagent.data.providers import fmp as _fmp  # noqa: F401

__all__ = ["DataProvider", "providers", "SymbolRouter"]
