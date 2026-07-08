"""Small, dependency-free technical indicators.

Kept in core because both QuantFilters (selection) and EntryRules (timing) reuse
them. All functions take a list of floats (oldest -> newest) and return either a
scalar or a same-length list with ``None`` padding where undefined.
"""

from __future__ import annotations


def sma(values: list[float], window: int) -> float | None:
    """Simple moving average of the last ``window`` values."""

    if window <= 0 or len(values) < window:
        return None
    return sum(values[-window:]) / window


def roc(values: list[float], window: int) -> float | None:
    """Rate of change over ``window`` periods, as a fraction (0.1 == +10%)."""

    if window <= 0 or len(values) <= window:
        return None
    past = values[-window - 1]
    if past == 0:
        return None
    return values[-1] / past - 1.0


def atr(
    highs: list[float], lows: list[float], closes: list[float], window: int = 14
) -> float | None:
    """Average True Range over ``window`` periods (absolute, in price units)."""

    n = len(closes)
    if n <= window or len(highs) != n or len(lows) != n:
        return None
    trs: list[float] = []
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    if len(trs) < window:
        return None
    return sum(trs[-window:]) / window


def max_drawdown(values: list[float], window: int | None = None) -> float:
    """Largest peak-to-trough decline as a negative fraction (-0.2 == -20%)."""

    vals = values[-window:] if window else values
    if not vals:
        return 0.0
    peak = vals[0]
    mdd = 0.0
    for v in vals:
        peak = max(peak, v)
        if peak > 0:
            mdd = min(mdd, v / peak - 1.0)
    return mdd


def rsi(values: list[float], window: int = 14) -> float | None:
    """Wilder's RSI over ``window`` periods (0..100)."""

    if len(values) <= window:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(-window, 0):
        change = values[i] - values[i - 1]
        if change >= 0:
            gains += change
        else:
            losses -= change
    avg_gain = gains / window
    avg_loss = losses / window
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)
