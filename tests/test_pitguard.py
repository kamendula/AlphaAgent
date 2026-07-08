from datetime import date

import pytest

from alphaagent.agents.pitguard import (
    GuardedRouter,
    PITViolation,
    enforce_grounding,
    leakage_probe,
    pseudonymize,
    scrub_text,
    wrap_router,
)
from alphaagent.core.models import AssetType, Bar, Opinion, PriceSeries
from alphaagent.data.router import SymbolRouter
from alphaagent.llm.mock import MockLLM


def _router() -> SymbolRouter:
    return SymbolRouter(
        preference={AssetType.EQUITY: ["demo"], AssetType.CRYPTO: ["demo"]}, fallback=False
    )


# --------------------------------------------------------------------------- #
# boundary
# --------------------------------------------------------------------------- #
def test_guarded_router_returns_only_bars_on_or_before_as_of():
    as_of = date(2024, 6, 28)
    guarded = wrap_router(_router(), as_of)

    series = guarded.get_prices("NVDA")
    assert isinstance(guarded, GuardedRouter)
    assert len(series) > 0
    assert all(bar.d <= as_of for bar in series.bars)
    assert series.last.d <= as_of


def test_guarded_router_forces_as_of_ignoring_caller_argument():
    guarded = wrap_router(_router(), date(2024, 6, 28))

    # Caller tries to widen the window to a later date; the guard must win.
    series = guarded.get_prices("NVDA", as_of=date(2024, 12, 31))
    assert series.last.d <= date(2024, 6, 28)


def test_guarded_router_raises_on_future_bar():
    class LeakyRouter:
        def get_prices(self, symbol, *, as_of=None, lookback=260):
            # Deliberately return a future bar, bypassing PriceSeries validation
            # by constructing it without as_of.
            future = Bar(date(2025, 1, 1), 1, 1, 1, 1, 1)
            return PriceSeries(symbol=symbol, bars=[future], as_of=None)

    guarded = GuardedRouter(LeakyRouter(), date(2024, 12, 31))
    with pytest.raises(PITViolation):
        guarded.get_prices("NVDA")


# --------------------------------------------------------------------------- #
# anonymize
# --------------------------------------------------------------------------- #
def test_pseudonymize_is_stable_and_opaque():
    p1 = pseudonymize("AAPL")
    p2 = pseudonymize("aapl")  # case-insensitive
    assert p1 == p2
    assert p1.startswith("SEC_")
    assert "AAPL" not in p1
    # Different symbols should (typically) map elsewhere.
    assert pseudonymize("NVDA") != p1 or pseudonymize("NVDA").startswith("SEC_")


def test_scrub_text_removes_symbol():
    text = "NVDA looks strong; buy NVDA-USD on the dip."
    out = scrub_text(text, "NVDA")
    assert "NVDA" not in out
    assert pseudonymize("NVDA") in out


# --------------------------------------------------------------------------- #
# evidence grounding
# --------------------------------------------------------------------------- #
def test_enforce_grounding_downgrades_ungrounded_opinion():
    op = Opinion(
        role="technical",
        stance="bullish",
        confidence=0.8,
        evidence_refs=["hallucinated:ref"],
        info_richness="A",
    )
    guarded = enforce_grounding(op, allowed_refs={"price:ohlcv"})
    assert guarded.evidence_refs == []
    assert guarded.confidence < 0.8
    assert guarded.info_richness == "C"


def test_enforce_grounding_keeps_valid_refs():
    op = Opinion(
        role="technical",
        stance="bullish",
        confidence=0.8,
        evidence_refs=["price:ohlcv", "bogus:ref"],
        info_richness="A",
    )
    guarded = enforce_grounding(op, allowed_refs={"price:ohlcv"})
    assert guarded.evidence_refs == ["price:ohlcv"]
    assert guarded.confidence == 0.8  # untouched when grounded
    assert guarded.info_richness == "A"


# --------------------------------------------------------------------------- #
# leakage probe
# --------------------------------------------------------------------------- #
def test_leakage_probe_on_mock_is_clean():
    result = leakage_probe(MockLLM(), date(2024, 12, 31))
    assert result.score <= 0.0
    assert result.contaminated is False
    assert result.as_of == date(2024, 12, 31)
