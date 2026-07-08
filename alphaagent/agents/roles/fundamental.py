"""Fundamental analyst — earnings/valuation quality.

Pulls a point-in-time fundamentals snapshot through the router (FMP live, or the
bundled offline snapshots) and reasons about EPS-growth acceleration, revenue
growth, margins and valuation. If no fundamentals are available (e.g. crypto, or
a report not yet filed as of the run date), it honestly abstains.
"""

from __future__ import annotations

from alphaagent.agents.base import Analyst, AnalystContext, analysts
from alphaagent.agents.prompting import ask_opinion
from alphaagent.core.models import Opinion


@analysts.register("fundamental")
class FundamentalAnalyst(Analyst):
    role = "fundamental"

    def analyze(self, symbol: str, ctx: AnalystContext) -> Opinion:
        try:
            f = ctx.router.get_fundamentals(symbol, as_of=ctx.as_of)
        except Exception as exc:  # noqa: BLE001 - no provider / crypto / not filed yet
            evidence = {"available": False, "note": f"no fundamentals ({type(exc).__name__})"}
            return ask_opinion(ctx, self.role, symbol, evidence)

        eps_g = list(f.eps_growth[:3])  # newest-first YoY growth per quarter
        accelerating = len(eps_g) >= 2 and all(
            eps_g[i] > eps_g[i + 1] for i in range(len(eps_g) - 1)
        )
        evidence = {
            "available": True,
            "eps_growth_recent": [round(x, 4) for x in eps_g],
            "eps_accelerating": accelerating,
            "revenue_growth": round(f.revenue_growth, 4) if f.revenue_growth is not None else None,
            "net_margin": round(f.net_margin, 4) if f.net_margin is not None else None,
            "pe": round(f.pe, 2) if f.pe is not None else None,
            "as_of_filing": f.latest_filing.isoformat() if f.latest_filing else None,
        }
        return ask_opinion(ctx, self.role, symbol, evidence)
