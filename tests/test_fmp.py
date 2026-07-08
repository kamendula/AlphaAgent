"""Offline tests for the FMP provider — no network, no API key.

We only check the bits that don't touch the wire: that importing the module
registers "fmp" on the providers registry, that it declares the expected asset
support, and that the crypto-symbol normalization helper behaves.
"""

from alphaagent.core.models import AssetType
from alphaagent.data.base import providers
from alphaagent.data.providers.fmp import FMPProvider, _to_fmp_symbol


def test_fmp_is_registered():
    assert "fmp" in providers
    assert providers.get("fmp") is FMPProvider
    assert AssetType.EQUITY in FMPProvider.supports
    assert AssetType.CRYPTO in FMPProvider.supports


def test_crypto_symbol_normalization():
    # Crypto pairs drop the separator to match FMP's convention.
    assert _to_fmp_symbol("BTC-USD") == "BTCUSD"
    assert _to_fmp_symbol("ETH/USDT") == "ETHUSDT"
    assert _to_fmp_symbol("btc-usd") == "BTCUSD"  # case-insensitive


def test_equity_symbol_passes_through():
    assert _to_fmp_symbol("AAPL") == "AAPL"
    assert _to_fmp_symbol("nvda") == "NVDA"


def test_missing_api_key_raises_without_network():
    # No key, no wire call: get_prices must fail fast before any urlopen.
    provider = FMPProvider(api_key=None)
    provider.api_key = None  # ensure a stray env var can't flip this test
    try:
        provider.get_prices("AAPL")
    except RuntimeError as exc:
        assert "FMP_API_KEY" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected RuntimeError when API key is unset")
