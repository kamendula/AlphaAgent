"""The BacktestAdapter contract, its registry, and the result model.

AlphaAgent backtests only the **mechanical** layer — the entry rule plus
deterministic exits, with the agent panel bypassed entirely. That keeps the
honesty guarantee: agent-parameter leakage can never touch a headline
performance number, because agents aren't in the loop being measured.

An adapter takes a single symbol's :class:`~alphaagent.core.models.PriceSeries`,
an :class:`~alphaagent.entry.base.EntryRule`, and a config dict, and returns a
:class:`BacktestResult`. The stdlib ``simple`` adapter is the default; a thin
``backtesting`` adapter wraps the third-party ``backtesting.py`` library as an
optional backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from alphaagent.core.models import PriceSeries
from alphaagent.core.registry import Registry
from alphaagent.entry.base import EntryRule

backtest_adapters: Registry[type["BacktestAdapter"]] = Registry("backtest-adapter")


@dataclass(slots=True)
class Trade:
    """A single round-trip trade recorded by a backtest.

    ``r`` is the P&L expressed in units of initial risk (R multiple):
    ``r = pnl / (entry_price - stop_price)``. A trade that hit its stop is
    ~ ``-1R``; a 2R take-profit target is ``+2R``.
    """

    symbol: str
    entry_date: date
    entry_price: float
    exit_date: date
    exit_price: float
    pnl: float  # per-share P&L in price units
    r: float
    reason: str = ""  # why it exited: stop / target / time / eod


@dataclass(slots=True)
class BacktestResult:
    """Summary statistics for a mechanical backtest run.

    All ratios are guarded to be well-defined on empty inputs (no trades ->
    zeroes), so callers and tests can rely on sane, bounded fields.
    """

    symbol: str
    trades: list[Trade] = field(default_factory=list)
    win_rate: float = 0.0  # 0..1
    avg_win_R: float = 0.0
    avg_loss_R: float = 0.0  # signed (typically negative)
    expectancy: float = 0.0  # mean R across all trades
    num_trades: int = 0
    equity_curve: list[float] = field(default_factory=list)  # cumulative R

    @classmethod
    def from_trades(cls, symbol: str, trades: list[Trade]) -> "BacktestResult":
        """Compute the summary stats from a list of trades."""

        n = len(trades)
        wins = [t.r for t in trades if t.r > 0]
        losses = [t.r for t in trades if t.r <= 0]
        rs = [t.r for t in trades]

        equity: list[float] = []
        running = 0.0
        for r in rs:
            running += r
            equity.append(round(running, 4))

        return cls(
            symbol=symbol,
            trades=trades,
            win_rate=round(len(wins) / n, 4) if n else 0.0,
            avg_win_R=round(sum(wins) / len(wins), 4) if wins else 0.0,
            avg_loss_R=round(sum(losses) / len(losses), 4) if losses else 0.0,
            expectancy=round(sum(rs) / n, 4) if n else 0.0,
            num_trades=n,
            equity_curve=equity,
        )


class BacktestAdapter(ABC):
    """Replays an entry rule over historical bars and scores the result."""

    def __init__(self, **config: Any) -> None:
        self.config = config

    @abstractmethod
    def run(
        self,
        series: PriceSeries,
        entry_rule: EntryRule,
        config: dict[str, Any] | None = None,
    ) -> BacktestResult:
        """Backtest ``entry_rule`` over ``series`` and return a summary."""
