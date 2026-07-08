"""Live provider backed by Financial Modeling Prep (FMP).

Uses the stdlib (``urllib`` + ``json``) — no third-party HTTP library — so it
adds no install burden; it only needs network access and an API key at runtime.

Set the key via environment (``.env`` is auto-loaded by the CLI)::

    FMP_API_KEY=your_key_here

Config::

    [data.providers]
    equity = ["fmp"]
    crypto = ["fmp"]

    [filter]
    source = "trend"

Endpoint: v3 ``historical-price-full`` (daily OHLCV). Crypto symbols are
normalized to FMP's convention (``BTC-USD`` / ``ETH/USDT`` -> ``BTCUSD`` /
``ETHUSDT``).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

from alphaagent.core.models import (
    AssetType,
    Bar,
    Fundamentals,
    NewsFeed,
    NewsItem,
    PriceSeries,
)
from alphaagent.data.base import DataProvider, providers
from alphaagent.data.router import classify

# FMP's current ("stable") daily EOD endpoint. The legacy /api/v3/
# historical-price-full path now returns 403 on current keys.
_BASE = "https://financialmodelingprep.com/stable/historical-price-eod/full"


@providers.register("fmp")
class FMPProvider(DataProvider):
    """Fetches daily OHLCV from Financial Modeling Prep."""

    supports = (AssetType.EQUITY, AssetType.CRYPTO)

    def __init__(self, api_key: str | None = None, timeout: float = 15.0) -> None:
        # Config value wins, else environment.
        self.api_key = api_key or os.environ.get("FMP_API_KEY")
        self.timeout = timeout

    def get_prices(
        self, symbol: str, *, as_of: date | None = None, lookback: int = 260
    ) -> PriceSeries:
        if not self.api_key:
            raise RuntimeError(
                "FMP_API_KEY is not set; export it or put it in .env "
                "(or use the offline 'demo' provider)"
            )

        fmp_symbol = _to_fmp_symbol(symbol)
        end = as_of or date.today()
        start = end - timedelta(days=int(lookback * 1.7) + 10)
        query = urllib.parse.urlencode(
            {
                "symbol": fmp_symbol,
                "from": start.isoformat(),
                "to": end.isoformat(),
                "apikey": self.api_key,
            }
        )
        url = f"{_BASE}?{query}"

        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            raise RuntimeError(f"FMP HTTP {exc.code} for {fmp_symbol!r}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network
            raise RuntimeError(f"FMP request failed for {fmp_symbol!r}: {exc.reason}") from exc

        # The stable endpoint returns a bare list of daily bars (newest first).
        history = payload if isinstance(payload, list) else payload.get("historical")
        if not history:
            raise ValueError(f"FMP returned no history for {fmp_symbol!r}")

        bars: list[Bar] = []
        for row in history:
            d = date.fromisoformat(row["date"][:10])
            if as_of is not None and d > as_of:
                continue
            bars.append(
                Bar(
                    d=d,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume") or 0.0),
                )
            )

        bars.sort(key=lambda b: b.d)  # FMP returns newest-first
        if lookback and len(bars) > lookback:
            bars = bars[-lookback:]
        if not bars:
            raise ValueError(f"no bars for {fmp_symbol!r} on/before as_of={as_of}")
        return PriceSeries(symbol=symbol.upper(), bars=bars, as_of=as_of)

    def get_fundamentals(
        self, symbol: str, *, as_of: date | None = None
    ) -> Fundamentals:
        if not self.api_key:
            raise RuntimeError("FMP_API_KEY is not set")
        if classify(symbol) is AssetType.CRYPTO:
            raise NotImplementedError("crypto has no fundamentals")

        sym = _to_fmp_symbol(symbol)
        income = self._get_list("income-statement", sym, limit=16)
        ratios = self._get_list("ratios", sym, limit=16)

        # PIT gate: a quarter is "known" only once its statement was filed on or
        # before as_of. Keep filed rows, newest first.
        filed = []
        for r in income:
            fd, d = r.get("filingDate"), r.get("date")
            if not (fd and d):
                continue
            filing = date.fromisoformat(fd[:10])
            if as_of is None or filing <= as_of:
                filed.append((date.fromisoformat(d[:10]), filing, r))
        filed.sort(key=lambda x: x[0], reverse=True)
        if not filed:
            raise ValueError(f"no fundamentals known for {sym!r} as of {as_of}")

        # Year-over-year growth: compare each quarter to the same quarter a year
        # earlier (4 quarters back), NOT sequentially — so seasonal businesses
        # aren't punished for an off-quarter. Needs >= 5 quarters of history.
        eps = [_num(r.get("eps")) for _, _, r in filed]
        rev = [_num(r.get("revenue")) for _, _, r in filed]
        eps_growth = tuple(
            eps[i] / eps[i + 4] - 1.0
            for i in range(len(eps) - 4)
            if eps[i] is not None and eps[i + 4] not in (None, 0) and eps[i + 4] > 0
        )
        rev_growth = (
            rev[0] / rev[4] - 1.0
            if len(rev) > 4 and rev[0] is not None and rev[4] not in (None, 0)
            else None
        )

        # Margin / valuation from the latest ratios row that is also PIT-known.
        known_periods = {d.isoformat() for d, _, _ in filed}
        ratios_known = [r for r in ratios if r.get("date", "")[:10] in known_periods]
        net_margin = _num(ratios_known[0].get("netProfitMargin")) if ratios_known else None
        pe = _num(ratios_known[0].get("priceToEarningsRatio")) if ratios_known else None

        latest_period, latest_filing, _ = filed[0]
        return Fundamentals(
            symbol=symbol.upper(),
            as_of=as_of,
            eps_growth=eps_growth,
            revenue_growth=rev_growth,
            net_margin=net_margin,
            pe=pe,
            latest_period=latest_period,
            latest_filing=latest_filing,
        )

    def get_news(
        self, symbol: str, *, as_of: date | None = None, limit: int = 20
    ) -> NewsFeed:
        if not self.api_key:
            raise RuntimeError("FMP_API_KEY is not set")
        sym = _to_fmp_symbol(symbol)
        query = urllib.parse.urlencode(
            {"symbols": sym, "limit": max(limit, 50), "apikey": self.api_key}
        )
        url = f"https://financialmodelingprep.com/stable/news/stock?{query}"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                rows = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            raise RuntimeError(f"FMP news HTTP {exc.code} for {sym!r}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network
            raise RuntimeError(f"FMP news failed for {sym!r}: {exc.reason}") from exc

        items: list[NewsItem] = []
        for r in rows if isinstance(rows, list) else []:
            pub = r.get("publishedDate")
            if not pub:
                continue
            d = date.fromisoformat(pub[:10])
            if as_of is not None and d > as_of:
                continue  # PIT: not published yet as of the boundary
            items.append(
                NewsItem(
                    d=d,
                    title=(r.get("title") or "").strip(),
                    site=r.get("site") or r.get("publisher") or "",
                    url=r.get("url") or "",
                    summary=(r.get("text") or "")[:280],
                )
            )
        items.sort(key=lambda x: x.d, reverse=True)
        if not items:
            raise ValueError(f"no news for {sym!r} on/before as_of={as_of}")
        return NewsFeed(symbol=symbol.upper(), items=tuple(items[:limit]), as_of=as_of)

    def _get_list(self, endpoint: str, symbol: str, *, limit: int) -> list:
        query = urllib.parse.urlencode(
            {"symbol": symbol, "period": "quarter", "limit": limit, "apikey": self.api_key}
        )
        url = f"https://financialmodelingprep.com/stable/{endpoint}?{query}"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            raise RuntimeError(f"FMP HTTP {exc.code} for {endpoint} {symbol!r}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network
            raise RuntimeError(f"FMP {endpoint} failed for {symbol!r}: {exc.reason}") from exc
        return data if isinstance(data, list) else []


def _num(x) -> float | None:
    """Coerce an FMP field to float, or None if missing/unparseable."""
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _to_fmp_symbol(symbol: str) -> str:
    """FMP crypto pairs drop the separator (BTC-USD -> BTCUSD); equities pass through."""

    s = symbol.strip().upper()
    if classify(s) is AssetType.CRYPTO:
        return s.replace("-", "").replace("/", "")
    return s
