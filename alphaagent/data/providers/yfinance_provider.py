"""Live equity/crypto provider backed by yfinance.

Optional: ``yfinance`` is imported lazily, so the demo path never needs it.
Install with ``pip install "alphaagent[live]"``.
"""

from __future__ import annotations

from datetime import date, timedelta

from alphaagent.core.models import AssetType, Bar, PriceSeries
from alphaagent.data.base import DataProvider, providers


@providers.register("yfinance")
class YFinanceProvider(DataProvider):
    """Fetches daily OHLCV from Yahoo Finance (no API key required)."""

    supports = (AssetType.EQUITY, AssetType.CRYPTO)

    def get_prices(
        self, symbol: str, *, as_of: date | None = None, lookback: int = 260
    ) -> PriceSeries:
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise RuntimeError(
                "yfinance is not installed; run `pip install \"alphaagent[live]\"` "
                "or use the offline 'demo' provider"
            ) from exc

        end = (as_of or date.today()) + timedelta(days=1)
        # Over-fetch calendar days to cover weekends/holidays, then trim.
        start = end - timedelta(days=int(lookback * 1.7) + 10)

        df = yf.download(
            symbol,
            start=start.isoformat(),
            end=end.isoformat(),
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        if df is None or df.empty:
            raise ValueError(f"yfinance returned no data for {symbol!r}")

        bars: list[Bar] = []
        for idx, row in df.iterrows():
            d = idx.date() if hasattr(idx, "date") else date.fromisoformat(str(idx)[:10])
            if as_of is not None and d > as_of:
                continue
            bars.append(
                Bar(
                    d=d,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row["Volume"]),
                )
            )

        bars.sort(key=lambda b: b.d)
        if lookback and len(bars) > lookback:
            bars = bars[-lookback:]
        if not bars:
            raise ValueError(f"no bars for {symbol!r} on/before as_of={as_of}")
        return PriceSeries(symbol=symbol.upper(), bars=bars, as_of=as_of)
