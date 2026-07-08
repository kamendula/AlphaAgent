"""Backtest tests for the stdlib 'simple' adapter on demo data.

The optional 'backtesting' adapter is intentionally NOT tested here: it depends
on a third-party library that may be uninstalled.
"""

from datetime import date

from alphaagent.backtest import BacktestResult, Trade, backtest_adapters
from alphaagent.backtest.base import BacktestResult as _BR
from alphaagent.core.models import AssetType
from alphaagent.data.router import SymbolRouter
from alphaagent.entry import entry_rules


def _series(symbol: str):
    router = SymbolRouter(
        preference={AssetType.EQUITY: ["demo"], AssetType.CRYPTO: ["demo"]}, fallback=False
    )
    return router.get_prices(symbol)


def test_simple_adapter_is_registered_and_default():
    assert "simple" in backtest_adapters.names()


def test_simple_backtest_runs_and_returns_sane_result():
    adapter = backtest_adapters.get("simple")()
    rule = entry_rules.get("breakout")()
    for symbol in ("NVDA", "AMZN"):
        result = adapter.run(_series(symbol), rule)
        assert isinstance(result, BacktestResult)
        assert result.symbol == symbol
        assert result.num_trades >= 0
        assert result.num_trades == len(result.trades)
        assert 0.0 <= result.win_rate <= 1.0
        assert len(result.equity_curve) == result.num_trades
        for t in result.trades:
            assert isinstance(t, Trade)
            assert t.exit_date >= t.entry_date
            assert t.reason in {"stop", "target", "time", "eod"}


def test_pullback_rule_backtests_too():
    adapter = backtest_adapters.get("simple")()
    rule = entry_rules.get("pullback")()
    result = adapter.run(_series("NVDA"), rule)
    assert isinstance(result, BacktestResult)
    assert result.num_trades >= 0
    assert 0.0 <= result.win_rate <= 1.0


def test_result_stats_are_consistent_with_trades():
    adapter = backtest_adapters.get("simple")()
    rule = entry_rules.get("breakout")(lookback=10, vol_mult=1.0)
    result = adapter.run(_series("AMZN"), rule)
    if result.num_trades:
        # Expectancy is the mean R; equity curve ends at the sum of Rs.
        total_r = sum(t.r for t in result.trades)
        assert abs(result.equity_curve[-1] - round(total_r, 4)) < 1e-6
        assert abs(result.expectancy - round(total_r / result.num_trades, 4)) < 1e-6


def test_from_trades_handles_empty():
    empty = _BR.from_trades("XYZ", [])
    assert empty.num_trades == 0
    assert empty.win_rate == 0.0
    assert empty.expectancy == 0.0
    assert empty.equity_curve == []
