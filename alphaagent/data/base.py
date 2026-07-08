"""The DataProvider contract and its registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from alphaagent.core.models import AssetType, Fundamentals, NewsFeed, PriceSeries
from alphaagent.core.registry import Registry

# The one registry every data source plugs into.
providers: Registry[type["DataProvider"]] = Registry("data-provider")


class DataProvider(ABC):
    """Fetches point-in-time market data for a symbol.

    Concrete providers implement :meth:`get_prices`. ``as_of`` is honoured as a
    hard boundary: a provider must not return any bar dated after it. (The demo
    provider enforces this via :class:`PriceSeries`; live providers should slice
    before returning.)
    """

    #: Asset classes this provider can serve. Used by the router as a filter.
    supports: tuple[AssetType, ...] = ()

    @abstractmethod
    def get_prices(
        self, symbol: str, *, as_of: date | None = None, lookback: int = 260
    ) -> PriceSeries:
        """Return up to ``lookback`` daily OHLCV bars ending on/before ``as_of``."""

    def get_fundamentals(
        self, symbol: str, *, as_of: date | None = None
    ) -> Fundamentals:
        """Return a point-in-time fundamentals snapshot.

        Optional capability: providers without fundamentals raise
        :class:`NotImplementedError` (the default), and the router/analyst treat
        that as "no fundamentals available" rather than an error.
        """

        raise NotImplementedError(
            f"{type(self).__name__} does not provide fundamentals"
        )

    def get_news(
        self, symbol: str, *, as_of: date | None = None, limit: int = 20
    ) -> NewsFeed:
        """Return recent news published on/before ``as_of`` (newest first).

        Optional capability; providers without news raise
        :class:`NotImplementedError` (the default).
        """

        raise NotImplementedError(f"{type(self).__name__} does not provide news")

    # Room to grow: get_insider(), ... land later.
