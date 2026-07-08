"""The simplest pool source: a fixed list of symbols from config.

Config shape::

    pool:
      - source: watchlist
        symbols: [AAPL, MSFT, NVDA, BTC-USD]
        tag: my-list        # optional, defaults to "watchlist"
"""

from __future__ import annotations

from alphaagent.core.models import Candidate
from alphaagent.data.router import classify
from alphaagent.pool.base import PoolSource, pool_sources


@pool_sources.register("watchlist")
class WatchlistPool(PoolSource):
    def fetch(self) -> list[Candidate]:
        symbols = self.config.get("symbols", [])
        tag = self.config.get("tag", "watchlist")
        return [
            Candidate(
                symbol=str(s).upper(),
                asset_type=classify(str(s)),
                source_tags=[tag],
            )
            for s in symbols
        ]
