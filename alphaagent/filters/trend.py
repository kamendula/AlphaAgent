"""A starter trend/momentum filter.

Scores each candidate on three transparent factors and keeps those clearing a
threshold. Intentionally simple — it exists to demonstrate the contract and give
contributors a template, not to be a great strategy.

Factors (each roughly 0..1, then averaged):
  * ``trend``     — close above its SMA(50), scaled by distance
  * ``momentum``  — 60-day rate of change
  * ``not_overbought`` — RSI(14) headroom below 70

Config::

    filter:
      source: trend
      min_score: 0.5
      sma_window: 50
      roc_window: 60
"""

from __future__ import annotations

from datetime import date

from alphaagent.core.indicators import roc, rsi, sma
from alphaagent.core.models import Candidate, ScoredRow, ScoredTable
from alphaagent.data.router import SymbolRouter
from alphaagent.filters.base import QuantFilter, filters


@filters.register("trend")
class TrendFilter(QuantFilter):
    def score(
        self,
        candidates: list[Candidate],
        router: SymbolRouter,
        *,
        as_of: date | None = None,
    ) -> ScoredTable:
        min_score = float(self.config.get("min_score", 0.5))
        sma_window = int(self.config.get("sma_window", 50))
        roc_window = int(self.config.get("roc_window", 60))

        rows: ScoredTable = []
        for cand in candidates:
            try:
                series = router.get_prices(cand.symbol, as_of=as_of)
            except Exception as exc:  # noqa: BLE001 - skip unresolvable symbols
                rows.append(
                    ScoredRow(
                        symbol=cand.symbol,
                        asset_type=cand.asset_type,
                        score=0.0,
                        source_tags=cand.source_tags,
                        notes=f"no data: {exc}",
                    )
                )
                continue

            closes = series.closes
            last = closes[-1]
            ma = sma(closes, sma_window)
            momentum = roc(closes, roc_window)
            strength = rsi(closes, 14)

            trend_f = _clip((last / ma - 1.0) * 5 + 0.5) if ma else 0.0
            mom_f = _clip((momentum or 0.0) * 2 + 0.5)
            rsi_f = _clip((70 - strength) / 40) if strength is not None else 0.5

            # Resonance bonus: candidates surfaced by multiple pool sources.
            resonance = min(0.1 * (len(cand.source_tags) - 1), 0.2)
            base = (trend_f + mom_f + rsi_f) / 3
            score = round(min(base + resonance, 1.0), 4)

            rows.append(
                ScoredRow(
                    symbol=cand.symbol,
                    asset_type=cand.asset_type,
                    score=score,
                    factors={
                        "trend": round(trend_f, 3),
                        "momentum": round(mom_f, 3),
                        "not_overbought": round(rsi_f, 3),
                        "resonance": round(resonance, 3),
                    },
                    source_tags=cand.source_tags,
                    notes=f"close={last:.2f} sma{sma_window}={ma:.2f} rsi={strength:.1f}"
                    if ma and strength is not None
                    else "insufficient history",
                )
            )

        rows.sort(key=lambda r: r.score, reverse=True)
        return [r for r in rows if r.score >= min_score]


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))
