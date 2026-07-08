"""Optional adapter over the third-party ``backtesting.py`` library.

An optional backend over an established OSS backtester. It is a thin, best-effort
wrapper: it translates our :class:`~alphaagent.core.models.PriceSeries` into the
pandas DataFrame ``backtesting.py`` expects, drives the entry rule bar by bar
inside a ``Strategy``, and maps the library's stats back onto our
:class:`BacktestResult`.

The dependency is **lazily** imported inside :meth:`run` so the demo path — and
every other adapter — stays stdlib-only. If ``backtesting`` (and its pandas
dependency) are not installed, a clear, actionable error is raised.

Install with::

    pip install alphaagent[backtest]      # or: pip install backtesting
"""

from __future__ import annotations

from typing import Any

from alphaagent.backtest.base import (
    BacktestAdapter,
    BacktestResult,
    Trade,
    backtest_adapters,
)
from alphaagent.core.models import PriceSeries
from alphaagent.entry.base import EntryRule


@backtest_adapters.register("backtesting")
class BacktestingPyAdapter(BacktestAdapter):
    """Runs a mechanical entry rule through the ``backtesting.py`` engine."""

    def run(
        self,
        series: PriceSeries,
        entry_rule: EntryRule,
        config: dict[str, Any] | None = None,
    ) -> BacktestResult:
        try:
            import pandas as pd  # noqa: F401
            from backtesting import Backtest, Strategy
        except ImportError as exc:  # pragma: no cover - depends on optional dep
            raise ImportError(
                "the 'backtesting' adapter requires the third-party "
                "'backtesting.py' library (and pandas). Install with "
                "`pip install alphaagent[backtest]` or `pip install backtesting`. "
                "The default stdlib-only 'simple' adapter needs no extra install."
            ) from exc

        cfg = {**self.config, **(config or {})}
        tp_R = float(cfg.get("tp_R", 2.0))
        max_bars = int(cfg.get("max_bars", 20))
        warmup = int(cfg.get("warmup", 60))
        cash = float(cfg.get("cash", 100_000))

        symbol = series.symbol
        # backtesting.py wants a Datetime-indexed OHLCV frame (capitalised cols).
        df = pd.DataFrame(
            {
                "Open": [b.open for b in series.bars],
                "High": [b.high for b in series.bars],
                "Low": [b.low for b in series.bars],
                "Close": [b.close for b in series.bars],
                "Volume": [b.volume for b in series.bars],
            },
            index=pd.to_datetime([b.d for b in series.bars]),
        )
        bars = series.bars

        class _RuleStrategy(Strategy):
            def init(self) -> None:  # noqa: D401 - library hook
                self._entry_bar = -1
                self._risk = 0.0

            def next(self) -> None:  # noqa: D401 - library hook
                idx = len(self.data.Close) - 1
                if idx < warmup:
                    return

                if self.position:
                    if idx - self._entry_bar >= max_bars:
                        self.position.close()
                    return

                window = PriceSeries(
                    symbol=symbol, bars=bars[: idx + 1], as_of=bars[idx].d
                )
                sig = entry_rule.signal(symbol, _one(window), as_of=bars[idx].d)
                if sig.action != "buy":
                    return

                price = float(self.data.Close[-1])
                stop = sig.stop_hint if sig.stop_hint and sig.stop_hint < price else price * 0.95
                risk = price - stop
                if risk <= 0:
                    return
                self._entry_bar = idx
                self.buy(sl=stop, tp=price + tp_R * risk)

        bt = Backtest(df, _RuleStrategy, cash=cash, commission=0.0, finalize_trades=True)
        stats = bt.run()

        trades = _map_trades(symbol, stats._trades)
        return BacktestResult.from_trades(symbol, trades)


class _one:
    """Minimal router shim yielding one frozen series (mirrors simple.py)."""

    def __init__(self, series: PriceSeries) -> None:
        self._series = series

    def get_prices(self, symbol: str, *, as_of=None, lookback: int = 260) -> PriceSeries:
        return self._series


def _map_trades(symbol: str, tdf: Any) -> list[Trade]:
    """Map a ``backtesting.py`` trades DataFrame onto our Trade model."""

    trades: list[Trade] = []
    if tdf is None or len(tdf) == 0:
        return trades
    for _, row in tdf.iterrows():
        entry_price = float(row["EntryPrice"])
        exit_price = float(row["ExitPrice"])
        pnl = exit_price - entry_price
        # backtesting.py doesn't expose our initial risk, so approximate R off
        # the realised return; good enough for a best-effort OSS wrapper.
        r = pnl / entry_price if entry_price else 0.0
        trades.append(
            Trade(
                symbol=symbol,
                entry_date=row["EntryTime"].date(),
                entry_price=round(entry_price, 4),
                exit_date=row["ExitTime"].date(),
                exit_price=round(exit_price, 4),
                pnl=round(pnl, 4),
                r=round(r, 4),
                reason="backtesting.py",
            )
        )
    return trades
