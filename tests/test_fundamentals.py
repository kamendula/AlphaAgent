from datetime import date

from alphaagent.agents.base import AnalystContext
from alphaagent.agents.roles.fundamental import FundamentalAnalyst
from alphaagent.core.models import AssetType
from alphaagent.data.router import SymbolRouter
from alphaagent.llm.mock import MockLLM


def _router():
    return SymbolRouter(
        preference={AssetType.EQUITY: ["demo"], AssetType.CRYPTO: ["demo"]}, fallback=False
    )


def test_demo_provider_serves_fundamentals():
    from alphaagent.data.providers.demo import DemoProvider

    f = DemoProvider().get_fundamentals("NVDA")
    assert f.symbol == "NVDA"
    assert f.eps_growth and f.eps_growth[0] > 0
    assert f.latest_filing == date(2024, 11, 1)


def test_fundamentals_pit_gate_hides_unfiled_report():
    from alphaagent.data.providers.demo import DemoProvider

    # as_of before the filing date -> not yet public -> refused.
    import pytest

    with pytest.raises(ValueError):
        DemoProvider().get_fundamentals("NVDA", as_of=date(2024, 10, 1))


def test_fundamental_analyst_lights_up_offline():
    ctx = AnalystContext(router=_router(), llm=MockLLM(), as_of=date(2024, 12, 31))
    op = FundamentalAnalyst().analyze("NVDA", ctx)
    # NVDA fundamentals are strong & accelerating -> bullish, real evidence (A).
    assert op.stance == "bullish"
    assert op.info_richness == "A"
    assert op.evidence_refs == ["fundamentals:financials"]


def test_fundamental_analyst_abstains_for_crypto():
    ctx = AnalystContext(router=_router(), llm=MockLLM(), as_of=date(2024, 12, 31))
    op = FundamentalAnalyst().analyze("BTC-USD", ctx)
    # No fundamentals for crypto -> honest abstention.
    assert op.info_richness == "C"
    assert op.confidence <= 0.3
