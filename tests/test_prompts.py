"""Regression guards for externalized personas.

We check that (a) every role's persona loads as non-empty text from its
``prompts/<role>.md`` file, and (b) externalizing the persona didn't break the
prompt contract — the offline TechnicalAnalyst (MockLLM + demo router) still
returns a valid, evidence-grounded Opinion.
"""

from datetime import date

import pytest

from alphaagent.agents.base import AnalystContext
from alphaagent.agents.prompting import load_persona
from alphaagent.core.models import AssetType
from alphaagent.data.router import SymbolRouter
from alphaagent.llm.mock import MockLLM


def _router() -> SymbolRouter:
    return SymbolRouter(
        preference={AssetType.EQUITY: ["demo"], AssetType.CRYPTO: ["demo"]}, fallback=False
    )


@pytest.mark.parametrize("role", ["fundamental", "technical", "sentiment", "risk"])
def test_load_persona_returns_nonempty(role):
    persona = load_persona(role)
    assert isinstance(persona, str)
    assert persona.strip()  # non-empty


def test_externalization_preserves_opinion_contract():
    from alphaagent.agents.roles.technical import TechnicalAnalyst

    ctx = AnalystContext(router=_router(), llm=MockLLM(), as_of=date(2024, 12, 31))
    op = TechnicalAnalyst().analyze("NVDA", ctx)
    assert op.role == "technical"
    assert op.stance in {"bullish", "neutral", "cautious", "bearish"}
    assert op.evidence_refs == ["price:ohlcv"]
    assert op.info_richness == "A"  # real price evidence flowed through
