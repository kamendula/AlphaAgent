"""Reference plugin: a custom QuantFilter in ~30 lines.

A quant filter scores candidates using objective, reproducible rules, pulling
whatever data it needs through the router (so it stays source-agnostic and
point-in-time correct). This one scores on a single factor — 60-day momentum —
to keep the contract obvious. To make it live, move it under
``alphaagent/filters/`` and import it from that package's ``__init__``.

Run this file directly (uses the offline demo provider) to see it work::

    python examples/custom_filter.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Make the repo importable when this file is run directly (python examples/...).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alphaagent.core.indicators import roc  # noqa: E402
from alphaagent.core.models import Candidate, ScoredRow, ScoredTable  # noqa: E402
from alphaagent.data.router import SymbolRouter  # noqa: E402
from alphaagent.filters.base import QuantFilter, filters  # noqa: E402


@filters.register("example_filter")
class ExampleFilter(QuantFilter):
    """Ranks candidates on a single factor: 60-day rate of change."""

    def score(
        self,
        candidates: list[Candidate],
        router: SymbolRouter,
        *,
        as_of: date | None = None,
    ) -> ScoredTable:
        window = int(self.config.get("roc_window", 60))
        rows: ScoredTable = []
        for cand in candidates:
            series = router.get_prices(cand.symbol, as_of=as_of)
            momentum = roc(series.closes, window) or 0.0
            # Squash momentum into a 0..1 score (0% -> 0.5, +50% -> ~1.0).
            score = max(0.0, min(1.0, momentum + 0.5))
            rows.append(
                ScoredRow(
                    symbol=cand.symbol,
                    asset_type=cand.asset_type,
                    score=round(score, 4),
                    factors={"momentum": round(momentum, 4)},
                    source_tags=cand.source_tags,
                    notes=f"roc{window}={momentum:+.1%}",
                )
            )
        rows.sort(key=lambda r: r.score, reverse=True)
        return rows


if __name__ == "__main__":
    # Wire the offline demo provider so this runs with zero network/keys.
    import alphaagent.data.providers.demo  # noqa: F401 - registers "demo"
    from alphaagent.core.models import AssetType
    from alphaagent.data.router import classify

    router = SymbolRouter(
        preference={AssetType.EQUITY: ["demo"], AssetType.CRYPTO: ["demo"]}
    )
    candidates = [
        Candidate(symbol=s, asset_type=classify(s), source_tags=["demo"])
        for s in ("NVDA", "AAPL", "MSFT")
    ]
    scored = filters.get("example_filter")().score(
        candidates, router, as_of=date(2024, 12, 31)
    )
    print("example_filter ranking (best first):")
    for r in scored:
        print(f"  {r.symbol:6s} score={r.score:.3f}  {r.notes}")
