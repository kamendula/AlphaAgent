from alphaagent.core.models import AssetType
from alphaagent.data.router import SymbolRouter, classify


def test_classify_equity_and_crypto():
    assert classify("AAPL") is AssetType.EQUITY
    assert classify("7203.T") is AssetType.EQUITY
    assert classify("BTC-USD") is AssetType.CRYPTO
    assert classify("ETH/USDT") is AssetType.CRYPTO
    assert classify("BTCUSDT") is AssetType.CRYPTO


def test_router_reads_demo_snapshots():
    router = SymbolRouter(preference={AssetType.EQUITY: ["demo"], AssetType.CRYPTO: ["demo"]}, fallback=False)
    series = router.get_prices("AAPL")
    assert series.symbol == "AAPL"
    assert len(series) > 100
    assert series.last.close > 0
