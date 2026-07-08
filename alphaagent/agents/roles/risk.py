"""Risk analyst — the designated skeptic (volatility, drawdown, extension).

Kept as a distinct contrarian role so the panel always hears the downside,
rather than converging on consensus optimism.
"""

from __future__ import annotations

from alphaagent.agents.base import Analyst, AnalystContext, analysts
from alphaagent.agents.prompting import ask_opinion
from alphaagent.core.indicators import atr, max_drawdown, rsi
from alphaagent.core.models import Opinion


@analysts.register("risk")
class RiskAnalyst(Analyst):
    role = "risk"

    def analyze(self, symbol: str, ctx: AnalystContext) -> Opinion:
        series = ctx.router.get_prices(symbol, as_of=ctx.as_of)
        highs = [b.high for b in series.bars]
        lows = [b.low for b in series.bars]
        closes = series.closes
        a = atr(highs, lows, closes, 14)
        evidence = {
            "atr_pct": round((a / closes[-1]), 4) if a and closes[-1] else 0.0,
            "max_drawdown_60d": round(max_drawdown(closes, 60), 4),
            "rsi14": round(rsi(closes, 14) or 0.0, 1),
        }
        return ask_opinion(ctx, self.role, symbol, evidence)
