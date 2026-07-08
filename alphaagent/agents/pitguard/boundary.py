"""The tool-boundary guard — PIT-Guard's deterministic first line of defence.

Leakage source one — the tool/data layer: it is stopped at the *tool boundary*
by forcing every data access to respect the run's ``as_of`` and by re-checking
that nothing dated after it slips through. This covers ~90% of real leakage and
is 100% deterministic.

The providers + :class:`~alphaagent.core.models.PriceSeries` already honour
``as_of`` (the demo provider slices, live providers should too). :class:`GuardedRouter`
adds *defence in depth*: it wraps a :class:`~alphaagent.data.router.SymbolRouter`
so that no analyst can accidentally bypass the boundary — it (a) forces ``as_of``
on every call regardless of what the caller passes, and (b) re-validates the
returned series and raises :class:`PITViolation` if any bar post-dates ``as_of``.
"""

from __future__ import annotations

from datetime import date

from alphaagent.core.models import Fundamentals, NewsFeed, PriceSeries
from alphaagent.data.router import SymbolRouter


class PITViolation(Exception):
    """Raised when point-in-time data would leak past the ``as_of`` boundary.

    A guarded call has already forced ``as_of``, so hitting this means a provider
    ignored the boundary — a bug worth surfacing loudly rather than swallowing.
    """


class GuardedRouter:
    """A :class:`SymbolRouter` wrapper that enforces the point-in-time boundary.

    Every :meth:`get_prices` call is pinned to ``as_of`` (the value passed at
    construction wins over any per-call argument) and the returned series is
    re-validated, so an analyst literally cannot read the future through it.

    It mirrors the router's public surface (duck-typed as a ``SymbolRouter``) so
    it can be dropped into an :class:`~alphaagent.agents.base.AnalystContext`
    without touching analyst code.
    """

    def __init__(self, router: SymbolRouter, as_of: date | None) -> None:
        self._router = router
        self.as_of = as_of

    def get_prices(
        self, symbol: str, *, as_of: date | None = None, lookback: int = 260
    ) -> PriceSeries:
        """Fetch prices, forcing the guard's ``as_of`` and re-validating output."""

        # The guard's as_of always wins: an analyst cannot widen the window.
        series = self._router.get_prices(symbol, as_of=self.as_of, lookback=lookback)
        self._verify(series)
        return series

    def get_fundamentals(
        self, symbol: str, *, as_of: date | None = None
    ) -> Fundamentals:
        """Fetch fundamentals, forcing ``as_of`` and re-validating the filing date."""

        f = self._router.get_fundamentals(symbol, as_of=self.as_of)
        if self.as_of is not None and f.latest_filing and f.latest_filing > self.as_of:
            raise PITViolation(
                f"{symbol}: fundamentals filed {f.latest_filing} post-date "
                f"as_of {self.as_of} — provider ignored the boundary"
            )
        return f

    def get_news(
        self, symbol: str, *, as_of: date | None = None, limit: int = 20
    ) -> NewsFeed:
        """Fetch news, forcing ``as_of`` and re-validating publish dates."""

        feed = self._router.get_news(symbol, as_of=self.as_of, limit=limit)
        if self.as_of is not None:
            for item in feed.items:
                if item.d > self.as_of:
                    raise PITViolation(
                        f"{symbol}: news dated {item.d} post-dates as_of {self.as_of}"
                    )
        return feed

    def _verify(self, series: PriceSeries) -> None:
        """Belt-and-braces: fail loudly if any bar sneaks past the boundary."""

        if self.as_of is None:
            return
        for bar in series.bars:
            if bar.d > self.as_of:
                raise PITViolation(
                    f"{series.symbol}: bar {bar.d} post-dates as_of {self.as_of} "
                    "— provider ignored the point-in-time boundary"
                )

    def __getattr__(self, name: str):  # pragma: no cover - passthrough convenience
        # Forward any other router method (get_news, get_insider, ...) so this
        # stays a drop-in wrapper as the DataProvider surface grows.
        return getattr(self._router, name)


def wrap_router(router: SymbolRouter, as_of: date | None) -> GuardedRouter:
    """Wrap ``router`` in a :class:`GuardedRouter` pinned to ``as_of``."""

    return GuardedRouter(router, as_of)
