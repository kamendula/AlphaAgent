"""Symbol classification + provider dispatch with a fallback chain.

A symbol's *shape* decides its asset class, the asset class decides an ordered
list of providers to try, and the first one that succeeds wins. New markets are
onboarded by adding a regex rule here plus a provider file — no changes to
callers.
"""

from __future__ import annotations

import re
from datetime import date

from alphaagent.core.models import AssetType, PriceSeries
from alphaagent.data.base import DataProvider, providers

# Ordered (pattern -> asset class) rules. First match wins.
_RULES: list[tuple[re.Pattern[str], AssetType]] = [
    # Common crypto spellings: BTC-USD, ETH/USDT, BTCUSDT, SOL-USD ...
    (re.compile(r"^[A-Z]{2,6}[-/]?(USD|USDT|USDC|BTC|ETH)$"), AssetType.CRYPTO),
    # Equity tickers: 1-5 letters, optional exchange suffix like AAPL or 7203.T
    (re.compile(r"^[A-Z]{1,5}(\.[A-Z]{1,3})?$"), AssetType.EQUITY),
    (re.compile(r"^\d{1,5}(\.[A-Z]{1,3})?$"), AssetType.EQUITY),
]


def classify(symbol: str) -> AssetType:
    """Infer the asset class of ``symbol`` from its shape."""

    s = symbol.strip().upper()
    for pattern, asset_type in _RULES:
        if pattern.match(s):
            return asset_type
    return AssetType.UNKNOWN


class SymbolRouter:
    """Routes a symbol to a working data provider.

    Parameters
    ----------
    preference:
        Optional ``{AssetType: [provider_name, ...]}`` override of the try-order.
        Anything not listed falls back to every registered provider that
        declares support for the symbol's asset class.
    fallback:
        When ``True`` (default), unlisted providers are appended as fallbacks.
        Set ``False`` to use *only* the preferred providers — useful for
        deterministic/offline runs and tests (no accidental network calls).
    """

    def __init__(
        self,
        preference: dict[AssetType, list[str]] | None = None,
        *,
        fallback: bool = True,
    ) -> None:
        self._preference = preference or {}
        self._fallback = fallback
        self._cache: dict[str, DataProvider] = {}

    def _instance(self, name: str) -> DataProvider:
        if name not in self._cache:
            self._cache[name] = providers.get(name)()
        return self._cache[name]

    def _chain(self, asset_type: AssetType) -> list[DataProvider]:
        names = list(self._preference.get(asset_type, []))
        if self._fallback:
            # Append any other providers that support this asset class.
            for name in providers.names():
                if name in names:
                    continue
                cls = providers.get(name)
                if not cls.supports or asset_type in cls.supports:
                    names.append(name)
        return [self._instance(n) for n in names]

    def get_prices(
        self, symbol: str, *, as_of: date | None = None, lookback: int = 260
    ) -> PriceSeries:
        """Try each candidate provider in order; return the first success."""

        asset_type = classify(symbol)
        chain = self._chain(asset_type)
        if not chain:
            raise LookupError(f"no data provider registered for {symbol!r} ({asset_type})")

        errors: list[str] = []
        for provider in chain:
            try:
                return provider.get_prices(symbol, as_of=as_of, lookback=lookback)
            except Exception as exc:  # noqa: BLE001 - fall through to next source
                errors.append(f"{type(provider).__name__}: {exc}")
        raise LookupError(
            f"all providers failed for {symbol!r}: " + " | ".join(errors)
        )

    def get_fundamentals(self, symbol: str, *, as_of: date | None = None):
        """Try each provider for a fundamentals snapshot; first success wins.

        Providers without fundamentals raise ``NotImplementedError`` and are
        skipped. If none can serve them, raises ``LookupError`` (the caller — the
        fundamental analyst — treats that as "abstain").
        """

        asset_type = classify(symbol)
        errors: list[str] = []
        for provider in self._chain(asset_type):
            try:
                return provider.get_fundamentals(symbol, as_of=as_of)
            except NotImplementedError:
                continue
            except Exception as exc:  # noqa: BLE001 - fall through to next source
                errors.append(f"{type(provider).__name__}: {exc}")
        raise LookupError(
            f"no fundamentals for {symbol!r}: " + (" | ".join(errors) or "unsupported")
        )

    def get_news(self, symbol: str, *, as_of: date | None = None, limit: int = 20):
        """Try each provider for a news feed; first success wins (else LookupError)."""

        asset_type = classify(symbol)
        errors: list[str] = []
        for provider in self._chain(asset_type):
            try:
                return provider.get_news(symbol, as_of=as_of, limit=limit)
            except NotImplementedError:
                continue
            except Exception as exc:  # noqa: BLE001 - fall through to next source
                errors.append(f"{type(provider).__name__}: {exc}")
        raise LookupError(
            f"no news for {symbol!r}: " + (" | ".join(errors) or "unsupported")
        )
