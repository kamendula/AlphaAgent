"""Reference plugin: a custom DataProvider in ~20 lines.

This is the whole contract. To make it live, you'd move it under
``alphaagent/data/providers/`` and import it from that package's ``__init__``.
Run this file directly to see it work::

    python examples/custom_provider.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

# Make the repo importable when this file is run directly (python examples/...).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alphaagent.core.models import AssetType, Bar, PriceSeries  # noqa: E402
from alphaagent.data.base import DataProvider, providers  # noqa: E402


@providers.register("flatline")
class FlatlineProvider(DataProvider):
    """Serves a constant-price series — useful for tests and demos."""

    supports = (AssetType.EQUITY, AssetType.CRYPTO)

    def get_prices(
        self, symbol: str, *, as_of: date | None = None, lookback: int = 260
    ) -> PriceSeries:
        end = as_of or date(2024, 12, 31)
        price = 100.0
        bars = [
            Bar(d=end - timedelta(days=lookback - 1 - i),
                open=price, high=price, low=price, close=price, volume=1_000)
            for i in range(lookback)
        ]
        return PriceSeries(symbol=symbol.upper(), bars=bars, as_of=as_of)


if __name__ == "__main__":
    series = providers.get("flatline")().get_prices("TEST", lookback=10)
    print(f"{series.symbol}: {len(series)} bars, last close = {series.last.close}")
