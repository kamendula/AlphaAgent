from datetime import date

from alphaagent.agents import build_orchestrator, build_llm, AnalystContext
from alphaagent.agents.policies.panel import PanelPolicy
from alphaagent.core.models import Opinion
from alphaagent.data.router import SymbolRouter
from alphaagent.llm.mock import MockLLM


def _router():
    from alphaagent.core.models import AssetType
    return SymbolRouter(
        preference={AssetType.EQUITY: ["demo"], AssetType.CRYPTO: ["demo"]}, fallback=False
    )


def test_technical_analyst_grounds_opinion_in_price():
    from alphaagent.agents.roles.technical import TechnicalAnalyst

    ctx = AnalystContext(router=_router(), llm=MockLLM(), as_of=date(2024, 12, 31))
    op = TechnicalAnalyst().analyze("NVDA", ctx)
    assert op.role == "technical"
    assert op.stance in {"bullish", "neutral", "cautious", "bearish"}
    assert op.evidence_refs == ["price:ohlcv"]
    assert op.info_richness == "A"  # it had real price evidence


def test_abstaining_roles_report_low_richness():
    # Crypto has no fundamentals/news -> the sentiment analyst abstains (richness C).
    from alphaagent.agents.roles.sentiment import SentimentAnalyst

    ctx = AnalystContext(router=_router(), llm=MockLLM())
    op = SentimentAnalyst().analyze("BTC-USD", ctx)
    assert op.info_richness == "C"  # no data -> honest abstention
    assert op.confidence <= 0.3


def test_panel_policy_aggregates_and_rates():
    ops = [
        Opinion(role="technical", stance="bullish", confidence=0.8, info_richness="A"),
        Opinion(role="risk", stance="cautious", confidence=0.5, info_richness="B"),
        Opinion(role="fundamental", stance="neutral", confidence=0.2, info_richness="C"),
    ]
    verdict = PanelPolicy().decide("NVDA", ops)
    assert verdict.symbol == "NVDA"
    assert verdict.rating in {"strong_buy", "buy", "watch", "avoid"}
    assert 0.0 <= verdict.confidence <= 1.0
    assert len(verdict.opinions) == 3


def test_orchestrator_runs_all_roles_offline():
    cfg = {"llm": "mock", "policy": "panel",
           "roles": ["technical", "risk", "fundamental", "sentiment"]}
    orch = build_orchestrator(cfg)
    ctx = AnalystContext(router=_router(), llm=build_llm(cfg), as_of=date(2024, 12, 31))
    verdicts = orch.run(["NVDA", "AMZN"], ctx)
    assert len(verdicts) == 2
    assert all(len(v.opinions) == 4 for v in verdicts)
