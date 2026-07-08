"""Tests for the ``debate`` collaboration policy.

All offline: the no-LLM path is fully deterministic, and the LLM path is driven
by tiny in-test stub clients so nothing touches the network.
"""

from alphaagent.agents.base import collaboration_policies
from alphaagent.agents.policies.debate import DebatePolicy
from alphaagent.core.models import Opinion, Verdict
from alphaagent.llm.base import LLMClient
from alphaagent.llm.mock import MockLLM

_RATINGS = {"strong_buy", "buy", "watch", "avoid"}


def _opinions():
    return [
        Opinion(role="technical", stance="bullish", confidence=0.8,
                rationale="uptrend intact", info_richness="A"),
        Opinion(role="risk", stance="cautious", confidence=0.5,
                rationale="elevated volatility", key_risks=["high ATR"],
                info_richness="B"),
        Opinion(role="fundamental", stance="neutral", confidence=0.2,
                info_richness="C"),
    ]


class _StubJudgeLLM(LLMClient):
    """Returns a valid verdict JSON (wrapped in noise, to test robustness)."""

    def chat(self, system: str, user: str) -> str:
        return (
            "After weighing the debate:\n"
            '{"rating": "buy", "confidence": 0.7, '
            '"key_support": ["bull thesis strongest"], "key_risks": ["macro"]}\n'
            "That is my ruling."
        )


class _JunkLLM(LLMClient):
    """Emits unparseable output, to exercise the deterministic fallback."""

    def chat(self, system: str, user: str) -> str:
        return "The bulls and bears both make points. No JSON here."


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
def test_debate_registered():
    assert "debate" in collaboration_policies


def test_debate_no_arg_construction_works():
    # Mirrors build_orchestrator's no-arg fallback construction.
    policy = collaboration_policies.get("debate")()
    v = policy.decide("NVDA", _opinions())
    assert isinstance(v, Verdict)
    assert v.rating in _RATINGS
    assert len(v.opinions) == 3


# --------------------------------------------------------------------------- #
# No-LLM (deterministic) path
# --------------------------------------------------------------------------- #
def test_debate_no_llm_returns_valid_verdict():
    v = DebatePolicy().decide("NVDA", _opinions())
    assert isinstance(v, Verdict)
    assert v.symbol == "NVDA"
    assert v.rating in _RATINGS
    assert 0.0 <= v.confidence <= 1.0
    assert len(v.opinions) == 3


def test_debate_no_llm_is_deterministic():
    a = DebatePolicy().decide("NVDA", _opinions())
    b = DebatePolicy().decide("NVDA", _opinions())
    assert (a.rating, a.confidence, a.key_support, a.key_risks) == (
        b.rating, b.confidence, b.key_support, b.key_risks
    )


def test_debate_bulls_win_landslide():
    ops = [
        Opinion(role="a", stance="bullish", confidence=0.9, info_richness="A"),
        Opinion(role="b", stance="bullish", confidence=0.8, info_richness="A"),
    ]
    assert DebatePolicy().decide("AAPL", ops).rating == "strong_buy"


def test_debate_bears_win_maps_to_avoid():
    ops = [
        Opinion(role="a", stance="bearish", confidence=0.9, info_richness="A",
                key_risks=["deep drawdown"]),
        Opinion(role="b", stance="cautious", confidence=0.7, info_richness="B"),
    ]
    assert DebatePolicy().decide("AAPL", ops).rating == "avoid"


def test_debate_empty_is_watch():
    v = DebatePolicy().decide("AAPL", [])
    assert v.rating == "watch"
    assert v.confidence == 0.0


# --------------------------------------------------------------------------- #
# LLM path
# --------------------------------------------------------------------------- #
def test_debate_uses_llm_when_provided():
    v = DebatePolicy(llm=_StubJudgeLLM()).decide("NVDA", _opinions())
    assert v.rating == "buy"
    assert v.confidence == 0.7
    assert "bull thesis strongest" in v.key_support
    # Analyst-raised risks survive alongside the judge's.
    assert "high ATR" in v.key_risks
    assert "macro" in v.key_risks


def test_debate_junk_output_falls_back():
    v = DebatePolicy(llm=_JunkLLM()).decide("NVDA", _opinions())
    assert isinstance(v, Verdict)
    assert v.rating in _RATINGS  # deterministic fallback, no crash
    assert len(v.opinions) == 3


def test_debate_with_mock_llm_is_robust():
    # MockLLM replies with opinion-shaped JSON (no "rating"), so debate detects
    # off-schema output and falls back to deterministic adjudication.
    v = DebatePolicy(llm=MockLLM()).decide("NVDA", _opinions())
    assert isinstance(v, Verdict)
    assert v.rating in _RATINGS


def test_debate_rounds_kwarg_accepted():
    # rounds is a prompt hint; must not break construction or the offline path.
    v = DebatePolicy(rounds=3).decide("NVDA", _opinions())
    assert v.rating in _RATINGS
