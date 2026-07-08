"""Technical analyst — reads price structure (trend, momentum, RSI)."""

from __future__ import annotations

from alphaagent.agents.base import Analyst, AnalystContext, analysts
from alphaagent.agents.prompting import ask_opinion
from alphaagent.core.indicators import roc, rsi, sma
from alphaagent.core.models import Opinion


@analysts.register("technical")
class TechnicalAnalyst(Analyst):
    role = "technical"

    def analyze(self, symbol: str, ctx: AnalystContext) -> Opinion:
        series = ctx.router.get_prices(symbol, as_of=ctx.as_of)
        closes = series.closes
        ma = sma(closes, 50)
        evidence = {
            "close": round(closes[-1], 2),
            "sma50": round(ma, 2) if ma else None,
            "above_sma50": bool(ma and closes[-1] > ma),
            "momentum_60d": round(roc(closes, 60) or 0.0, 4),
            "rsi14": round(rsi(closes, 14) or 0.0, 1),
            "bars": len(series),
        }
        return ask_opinion(ctx, self.role, symbol, evidence)
