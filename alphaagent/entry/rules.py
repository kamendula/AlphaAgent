"""Starter entry-timing rules: breakout and pullback.

Both are intentionally simple, transparent, and deterministic — they exist to
demonstrate the :class:`~alphaagent.entry.base.EntryRule` contract and to give
the mechanical backtester something real to replay, not to be great strategies.

Each rule reads only bars ending at ``as_of`` (point-in-time honest) and returns
an :class:`~alphaagent.core.models.EntrySignal` with a concrete
``trigger_price`` and ``stop_hint`` so a backtest can size risk in R multiples.

Config (shared)::

    entry:
      rule: breakout
      # breakout knobs
      lookback: 20            # N-day high to break above
      vol_window: 20          # average-volume window
      vol_mult: 1.5           # today's volume must be >= vol_mult * avg
      atr_window: 14
      atr_mult: 2.0           # stop = entry - atr_mult * ATR
      # pullback knobs
      trend_window: 50        # close must be above this SMA (uptrend intact)
      fast_ema: 10
      slow_ema: 21
      near_pct: 0.03          # "at the EMA" tolerance band
"""

from __future__ import annotations

from datetime import date

from alphaagent.core.indicators import atr, sma
from alphaagent.core.models import EntrySignal, PriceSeries
from alphaagent.data.router import SymbolRouter
from alphaagent.entry.base import EntryRule, entry_rules


@entry_rules.register("breakout")
class BreakoutRule(EntryRule):
    """Buy when the close breaks above the recent N-day high on volume.

    Fires ``buy`` when today's close is the highest close of the last
    ``lookback`` bars *and* today's volume clears ``vol_mult`` times the average.
    The trigger is today's close; the stop is ``atr_mult`` ATRs below it.
    """

    def signal(
        self,
        symbol: str,
        router: SymbolRouter,
        *,
        as_of: date | None = None,
    ) -> EntrySignal:
        lookback = int(self.config.get("lookback", 20))
        vol_window = int(self.config.get("vol_window", 20))
        vol_mult = float(self.config.get("vol_mult", 1.5))
        atr_window = int(self.config.get("atr_window", 14))
        atr_mult = float(self.config.get("atr_mult", 2.0))

        series = router.get_prices(symbol, as_of=as_of)
        if len(series) < lookback + 1:
            return EntrySignal(
                symbol=symbol, action="pass", rationale="insufficient history"
            )

        last = series.last
        closes = series.closes
        # Prior high excludes today, so equalling it doesn't count as a break.
        prior_high = max(closes[-lookback - 1 : -1])
        avg_vol = _avg([b.volume for b in series.bars], vol_window)

        broke_out = last.close > prior_high
        vol_ok = avg_vol is not None and last.volume >= vol_mult * avg_vol

        if broke_out and vol_ok:
            a = atr(
                [b.high for b in series.bars],
                [b.low for b in series.bars],
                closes,
                atr_window,
            )
            stop = round(last.close - atr_mult * a, 4) if a else None
            return EntrySignal(
                symbol=symbol,
                action="buy",
                trigger_price=round(last.close, 4),
                stop_hint=stop,
                rationale=(
                    f"close {last.close:.2f} broke {lookback}d high "
                    f"{prior_high:.2f} on volume {last.volume:.0f} "
                    f">= {vol_mult:g}x avg {avg_vol:.0f}"
                ),
            )

        if broke_out and not vol_ok:
            return EntrySignal(
                symbol=symbol,
                action="wait",
                trigger_price=round(prior_high, 4),
                rationale="broke high but volume too light — wait for confirmation",
            )
        return EntrySignal(
            symbol=symbol,
            action="wait",
            trigger_price=round(prior_high, 4),
            rationale=f"below {lookback}d high {prior_high:.2f}",
        )


@entry_rules.register("pullback")
class PullbackRule(EntryRule):
    """Buy a pullback to the fast/slow EMA inside an intact uptrend.

    Uptrend gate: close above SMA(``trend_window``). Then, when price has pulled
    back to within ``near_pct`` of the ``fast_ema``/``slow_ema`` band *and* is
    stabilising (today's close >= yesterday's close), fire ``buy``. The stop is
    just below the recent swing low.
    """

    def signal(
        self,
        symbol: str,
        router: SymbolRouter,
        *,
        as_of: date | None = None,
    ) -> EntrySignal:
        trend_window = int(self.config.get("trend_window", 50))
        fast = int(self.config.get("fast_ema", 10))
        slow = int(self.config.get("slow_ema", 21))
        near_pct = float(self.config.get("near_pct", 0.03))

        series = router.get_prices(symbol, as_of=as_of)
        closes = series.closes
        if len(closes) < max(trend_window, slow) + 2:
            return EntrySignal(
                symbol=symbol, action="pass", rationale="insufficient history"
            )

        last = closes[-1]
        trend_ma = sma(closes, trend_window)
        ema_fast = _ema(closes, fast)
        ema_slow = _ema(closes, slow)

        if trend_ma is None or last <= trend_ma:
            return EntrySignal(
                symbol=symbol,
                action="pass",
                rationale=f"uptrend broken (close {last:.2f} <= sma{trend_window})",
            )

        # Distance to the nearer of the two EMAs, as a fraction.
        near_ema = min(ema_fast, ema_slow, key=lambda e: abs(last - e))
        dist = abs(last - near_ema) / near_ema if near_ema else 1.0
        stabilising = last >= closes[-2]

        if dist <= near_pct and stabilising:
            swing_low = min(_lows(series)[-slow:])
            stop = round(swing_low * 0.99, 4)
            return EntrySignal(
                symbol=symbol,
                action="buy",
                trigger_price=round(last, 4),
                stop_hint=stop,
                rationale=(
                    f"uptrend intact, pulled back to EMA {near_ema:.2f} "
                    f"({dist * 100:.1f}% away) and stabilising"
                ),
            )
        if dist <= near_pct:
            return EntrySignal(
                symbol=symbol,
                action="wait",
                trigger_price=round(last, 4),
                rationale="at EMA support but still falling — wait for a green bar",
            )
        return EntrySignal(
            symbol=symbol,
            action="wait",
            trigger_price=round(near_ema, 4),
            rationale=f"extended {dist * 100:.1f}% above EMA — wait for a pullback",
        )


# --------------------------------------------------------------------------- #
# Small local helpers (kept here so we don't touch core/indicators.py).
# --------------------------------------------------------------------------- #
def _avg(values: list[float], window: int) -> float | None:
    """Mean of the last ``window`` values (None if not enough history)."""

    if window <= 0 or len(values) < window:
        return None
    return sum(values[-window:]) / window


def _ema(values: list[float], window: int) -> float:
    """Exponential moving average (final value), seeded with an SMA."""

    if window <= 0 or not values:
        return values[-1] if values else 0.0
    if len(values) < window:
        return sum(values) / len(values)
    k = 2.0 / (window + 1.0)
    ema = sum(values[:window]) / window  # SMA seed
    for v in values[window:]:
        ema = v * k + ema * (1.0 - k)
    return ema


def _lows(series: PriceSeries) -> list[float]:
    return [b.low for b in series.bars]
