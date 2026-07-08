"""Reference plugin: a custom PoolSource in ~20 lines.

A pool source proposes a candidate universe. This one just returns a small,
hardcoded watchlist — the simplest possible source, handy as a template. To make
it live, move it under ``alphaagent/pool/`` and import it from that package's
``__init__``. Run this file directly to see it work::

    python examples/custom_pool.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the repo importable when this file is run directly (python examples/...).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alphaagent.core.models import Candidate  # noqa: E402
from alphaagent.data.router import classify  # noqa: E402
from alphaagent.pool.base import PoolSource, pool_sources  # noqa: E402

# A tiny, hardcoded candidate universe — swap for your own screen/API.
_CANDIDATES = ["AAPL", "NVDA", "BTC-USD"]


@pool_sources.register("example_pool")
class ExamplePool(PoolSource):
    """Proposes a fixed, hardcoded shortlist of symbols."""

    def fetch(self) -> list[Candidate]:
        return [
            Candidate(
                symbol=s.upper(),
                asset_type=classify(s),
                source_tags=["example_pool"],
            )
            for s in _CANDIDATES
        ]


if __name__ == "__main__":
    candidates = pool_sources.get("example_pool")().fetch()
    print(f"example_pool proposed {len(candidates)} candidates:")
    for c in candidates:
        print(f"  {c.symbol:10s} {c.asset_type.value}")
