"""Offline demo provider — reads committed CSV snapshots from ``demo_data/``.

This is what powers ``make demo``: zero network, zero API keys, deterministic
output. CSV schema (one file per symbol, ``<SYMBOL>.csv``)::

    date,open,high,low,close,volume
    2024-01-02,100.0,101.2,99.4,100.8,1200000
    ...
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from alphaagent.core.models import (
    AssetType,
    Bar,
    Fundamentals,
    NewsFeed,
    NewsItem,
    PriceSeries,
)
from alphaagent.data.base import DataProvider, providers

# demo_data/ lives at the repo root: .../alphaagent/demo_data
_DEMO_DIR = Path(__file__).resolve().parents[3] / "demo_data"


@providers.register("demo")
class DemoProvider(DataProvider):
    """Serves OHLCV from bundled CSV snapshots (works for any asset class)."""

    supports = (AssetType.EQUITY, AssetType.CRYPTO)

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or _DEMO_DIR

    def get_prices(
        self, symbol: str, *, as_of: date | None = None, lookback: int = 260
    ) -> PriceSeries:
        path = self.data_dir / f"{symbol.upper()}.csv"
        if not path.exists():
            raise FileNotFoundError(f"no demo snapshot for {symbol!r} at {path}")

        bars: list[Bar] = []
        with path.open(newline="") as fh:
            for row in csv.DictReader(fh):
                d = date.fromisoformat(row["date"])
                if as_of is not None and d > as_of:
                    continue  # respect the point-in-time boundary
                bars.append(
                    Bar(
                        d=d,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]),
                    )
                )

        bars.sort(key=lambda b: b.d)
        if lookback and len(bars) > lookback:
            bars = bars[-lookback:]
        if not bars:
            raise ValueError(f"no bars for {symbol!r} on/before as_of={as_of}")
        return PriceSeries(symbol=symbol.upper(), bars=bars, as_of=as_of)

    def get_fundamentals(
        self, symbol: str, *, as_of: date | None = None
    ) -> Fundamentals:
        path = self.data_dir / "fundamentals" / f"{symbol.upper()}.json"
        if not path.exists():
            # e.g. crypto, or a symbol without a bundled snapshot -> no fundamentals.
            raise FileNotFoundError(f"no demo fundamentals for {symbol!r}")

        j = json.loads(path.read_text())
        filing = date.fromisoformat(j["latest_filing"])
        if as_of is not None and filing > as_of:
            # PIT: the report hadn't been filed yet as of the boundary.
            raise ValueError(
                f"no fundamentals for {symbol!r} filed on/before {as_of} "
                f"(latest filing {filing})"
            )
        return Fundamentals(
            symbol=symbol.upper(),
            as_of=as_of,
            eps_growth=tuple(j.get("eps_growth", [])),
            revenue_growth=j.get("revenue_growth"),
            net_margin=j.get("net_margin"),
            pe=j.get("pe"),
            latest_period=date.fromisoformat(j["latest_period"]) if j.get("latest_period") else None,
            latest_filing=filing,
        )

    def get_news(
        self, symbol: str, *, as_of: date | None = None, limit: int = 20
    ) -> NewsFeed:
        path = self.data_dir / "news" / f"{symbol.upper()}.json"
        if not path.exists():
            raise FileNotFoundError(f"no demo news for {symbol!r}")

        items: list[NewsItem] = []
        for r in json.loads(path.read_text()):
            d = date.fromisoformat(r["date"])
            if as_of is not None and d > as_of:
                continue  # PIT: not published yet
            items.append(
                NewsItem(d=d, title=r["title"], site=r.get("site", "demo"),
                         summary=r.get("summary", ""))
            )
        items.sort(key=lambda x: x.d, reverse=True)
        if not items:
            raise ValueError(f"no demo news for {symbol!r} on/before {as_of}")
        return NewsFeed(symbol=symbol.upper(), items=tuple(items[:limit]), as_of=as_of)
