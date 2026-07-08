"""Backtest adapters: measure the *mechanical* layer only.

A backtest replays an :class:`~alphaagent.entry.base.EntryRule` plus deterministic
exits over historical bars — the agent panel is bypassed entirely, so agent
leakage can never touch a performance number. The stdlib ``simple`` adapter is
the default; the optional ``backtesting`` adapter wraps the third-party
``backtesting.py`` OSS framework (lazily imported).
"""

from alphaagent.backtest.base import (
    BacktestAdapter,
    BacktestResult,
    Trade,
    backtest_adapters,
)

# Register the stdlib-only default. The optional backtesting.py adapter is
# imported lazily on demand (it needs a third-party lib) rather than at import
# time, so the demo path stays dependency-free.
from alphaagent.backtest import simple as _simple  # noqa: F401

__all__ = [
    "BacktestAdapter",
    "BacktestResult",
    "Trade",
    "backtest_adapters",
]
