from datetime import date

import pytest

from alphaagent.agents.base import AnalystContext
from alphaagent.agents.roles.sentiment import SentimentAnalyst, _tone
from alphaagent.core.models import AssetType
from alphaagent.data.router import SymbolRouter
from alphaagent.llm.mock import MockLLM


def _router():
    return SymbolRouter(
        preference={AssetType.EQUITY: ["demo"], AssetType.CRYPTO: ["demo"]}, fallback=False
    )


def test_tone_scorer_direction():
    assert _tone(["Revenue beats, analysts raise targets"]) > 0
    assert _tone(["Guidance disappoints as margins weaken"]) < 0
    assert _tone(["Company schedules annual meeting"]) == 0


def test_demo_provider_serves_news_pit():
    from alphaagent.data.providers.demo import DemoProvider

    feed = DemoProvider().get_news("NVDA")
    assert len(feed) >= 1 and feed.items[0].title
    # PIT: as_of before the earliest headline -> nothing available.
    with pytest.raises((ValueError, FileNotFoundError)):
        DemoProvider().get_news("NVDA", as_of=date(2000, 1, 1))


def test_sentiment_analyst_lights_up_offline():
    ctx = AnalystContext(router=_router(), llm=MockLLM(), as_of=date(2024, 12, 31))
    op = SentimentAnalyst().analyze("NVDA", ctx)  # positive demo headlines
    assert op.stance == "bullish"
    assert op.info_richness == "B"
    assert op.evidence_refs == ["news:headlines"]

    bear = SentimentAnalyst().analyze("AMZN", ctx)  # negative demo headlines
    assert bear.stance == "bearish"


def test_sentiment_abstains_when_no_news():
    ctx = AnalystContext(router=_router(), llm=MockLLM(), as_of=date(2024, 12, 31))
    op = SentimentAnalyst().analyze("BTC-USD", ctx)  # no demo news file
    assert op.info_richness == "C"
    assert op.confidence <= 0.3
