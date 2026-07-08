"""A stdlib-only mechanical backtester (the default adapter).

Walks a :class:`~alphaagent.core.models.PriceSeries` one bar at a time. On each
bar it asks the entry rule for a signal *using only the bars up to that day*
(point-in-time honest); when the rule says ``buy`` and we are flat, it enters at
the **next** bar's open. Each open position is then managed by three
deterministic exits:

  * **stop**    — intrabar low <= stop price (rule's ``stop_hint``, or
                  ``entry - atr_mult * ATR`` as a fallback);
  * **target**  — intrabar high >= ``entry + tp_R * initial_risk`` (a fixed R
                  take-profit, default 2R);
  * **time**    — held for ``max_bars`` bars, exit at that bar's close.

Every trade is booked in R multiples and fed to
:meth:`BacktestResult.from_trades`. No agent layer is involved — that is the
whole point of backtesting the mechanical layer.

Config (all optional)::

    [backtest]
    adapter = "simple"
    tp_R = 2.0          # take-profit at +2R
    max_bars = 20       # time-stop
    atr_window = 14     # ATR fallback stop
    atr_mult = 2.0
    warmup = 60         # bars to skip before the rule may fire
"""

from __future__ import annotations

from typing import Any

from alphaagent.backtest.base import BacktestAdapter, BacktestResult, Trade, backtest_adapters
from alphaagent.core.indicators import atr
from alphaagent.core.models import Bar, PriceSeries
from alphaagent.entry.base import EntryRule


class _FrozenSeriesRouter:
    """Router stand-in that always returns one pre-sliced series.

    The entry rule calls ``router.get_prices(symbol, as_of=...)``; during a
    backtest we hand it exactly the bars visible on the day being simulated, so
    the rule can't peek into the future. Cheaper and safer than re-querying a
    real provider per bar.
    """

    def __init__(self, series: PriceSeries) -> None:
        self._series = series

    def get_prices(self, symbol: str, *, as_of=None, lookback: int = 260) -> PriceSeries:
        return self._series


@backtest_adapters.register("simple")
class SimpleBacktester(BacktestAdapter):
    """Deterministic, dependency-free bar-by-bar backtester."""

    def run(
        self,
        series: PriceSeries,
        entry_rule: EntryRule,
        config: dict[str, Any] | None = None,
    ) -> BacktestResult:
        cfg = {**self.config, **(config or {})}
        tp_R = float(cfg.get("tp_R", 2.0))
        max_bars = int(cfg.get("max_bars", 20))
        atr_window = int(cfg.get("atr_window", 14))
        atr_mult = float(cfg.get("atr_mult", 2.0))
        warmup = int(cfg.get("warmup", 60))

        bars = series.bars
        n = len(bars)
        trades: list[Trade] = []

        # Position state.
        in_pos = False
        entry_i = 0
        entry_price = 0.0
        stop_price = 0.0
        risk = 0.0
        target_price = 0.0

        i = warmup
        while i < n:
            if not in_pos:
                # Ask the rule using only bars[0..i] (inclusive).
                window = PriceSeries(
                    symbol=series.symbol,
                    bars=bars[: i + 1],
                    as_of=bars[i].d,
                )
                signal = entry_rule.signal(
                    series.symbol, _FrozenSeriesRouter(window), as_of=bars[i].d
                )
                if signal.action == "buy" and i + 1 < n:
                    nxt = bars[i + 1]
                    entry_price = nxt.open
                    stop_price = _resolve_stop(
                        signal.stop_hint, entry_price, bars[: i + 1], atr_window, atr_mult
                    )
                    risk = entry_price - stop_price
                    if risk <= 0:
                        i += 1
                        continue  # degenerate stop, skip this signal
                    target_price = entry_price + tp_R * risk
                    entry_i = i + 1
                    in_pos = True
                    i += 1  # enter on the next bar; manage from there
                    continue
                i += 1
                continue

            # In a position: check exits on bar i (entry bar onward).
            bar = bars[i]
            held = i - entry_i
            exit_price: float | None = None
            reason = ""

            # Stop takes priority over target within the same bar (conservative).
            if bar.low <= stop_price:
                exit_price, reason = stop_price, "stop"
            elif bar.high >= target_price:
                exit_price, reason = target_price, "target"
            elif held >= max_bars:
                exit_price, reason = bar.close, "time"
            elif i == n - 1:
                exit_price, reason = bar.close, "eod"

            if exit_price is not None:
                pnl = exit_price - entry_price
                trades.append(
                    Trade(
                        symbol=series.symbol,
                        entry_date=bars[entry_i].d,
                        entry_price=round(entry_price, 4),
                        exit_date=bar.d,
                        exit_price=round(exit_price, 4),
                        pnl=round(pnl, 4),
                        r=round(pnl / risk, 4),
                        reason=reason,
                    )
                )
                in_pos = False
            i += 1

        return BacktestResult.from_trades(series.symbol, trades)


def _resolve_stop(
    stop_hint: float | None,
    entry_price: float,
    bars: list[Bar],
    atr_window: int,
    atr_mult: float,
) -> float:
    """Use the rule's stop hint if it is below entry; else fall back to ATR."""

    if stop_hint is not None and stop_hint < entry_price:
        return stop_hint
    a = atr(
        [b.high for b in bars],
        [b.low for b in bars],
        [b.close for b in bars],
        atr_window,
    )
    if a:
        return entry_price - atr_mult * a
    # Last resort: a flat 5% stop so risk is always well-defined.
    return entry_price * 0.95
