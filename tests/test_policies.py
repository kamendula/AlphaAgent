"""Tests for the vote + llm_judge collaboration policies.

All offline: the deterministic policies need no LLM, and the LLM path is driven
by a tiny in-test stub client so nothing touches the network.
"""

from alphaagent.agents.base import collaboration_policies
from alphaagent.agents.policies.llm_judge import LlmJudgePolicy
from alphaagent.agents.policies.vote import VotePolicy
from alphaagent.core.models import Opinion, Verdict
from alphaagent.llm.base import LLMClient
from alphaagent.llm.mock import MockLLM

_RATINGS = {"strong_buy", "buy", "watch", "avoid"}


def _opinions():
    return [
        Opinion(role="technical", stance="bullish", confidence=0.8,
                rationale="uptrend intact", info_richness="A"),
        Opinion(role="risk", stance="cautious", confidence=0.5,
                rationale="elevated volatility", key_risks=["high ATR"], info_richness="B"),
        Opinion(role="fundamental", stance="neutral", confidence=0.2, info_richness="C"),
    ]


class _StubJudgeLLM(LLMClient):
    """Returns a valid verdict JSON (wrapped in noise, to test robustness)."""

    def chat(self, system: str, user: str) -> str:
        return (
            "Here is my ruling:\n"
            '{"rating": "buy", "confidence": 0.72, '
            '"key_support": ["technical uptrend"], "key_risks": ["high ATR"]}\n'
            "Thanks for reading."
        )


class _JunkLLM(LLMClient):
    """Emits unparseable output, to exercise the deterministic fallback."""

    def chat(self, system: str, user: str) -> str:
        return "I cannot possibly decide. No JSON here."


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
def test_policies_registered():
    assert "vote" in collaboration_policies
    assert "llm_judge" in collaboration_policies


# --------------------------------------------------------------------------- #
# vote
# --------------------------------------------------------------------------- #
def test_vote_returns_valid_verdict():
    v = VotePolicy().decide("NVDA", _opinions())
    assert isinstance(v, Verdict)
    assert v.symbol == "NVDA"
    assert v.rating in _RATINGS
    assert 0.0 <= v.confidence <= 1.0
    assert len(v.opinions) == 3


def test_vote_bulls_win_landslide():
    ops = [
        Opinion(role="a", stance="bullish", confidence=0.9, info_richness="A"),
        Opinion(role="b", stance="bullish", confidence=0.8, info_richness="A"),
    ]
    v = VotePolicy().decide("AAPL", ops)
    assert v.rating == "strong_buy"


def test_vote_empty_is_watch():
    v = VotePolicy().decide("AAPL", [])
    assert v.rating == "watch"
    assert v.confidence == 0.0


# --------------------------------------------------------------------------- #
# llm_judge
# --------------------------------------------------------------------------- #
def test_llm_judge_no_arg_construction_falls_back():
    # This mirrors how build_orchestrator constructs policies today: no-arg.
    policy = collaboration_policies.get("llm_judge")()
    v = policy.decide("NVDA", _opinions())
    assert isinstance(v, Verdict)
    assert v.rating in _RATINGS
    assert len(v.opinions) == 3


def test_llm_judge_none_llm_matches_panel_fallback():
    v = LlmJudgePolicy(llm=None).decide("NVDA", _opinions())
    assert v.rating in _RATINGS
    assert 0.0 <= v.confidence <= 1.0


def test_llm_judge_uses_llm_when_provided():
    v = LlmJudgePolicy(llm=_StubJudgeLLM()).decide("NVDA", _opinions())
    assert v.rating == "buy"
    assert v.confidence == 0.72
    assert "technical uptrend" in v.key_support
    # Analyst-raised risks survive alongside the judge's.
    assert "high ATR" in v.key_risks


def test_llm_judge_junk_output_falls_back():
    v = LlmJudgePolicy(llm=_JunkLLM()).decide("NVDA", _opinions())
    assert v.rating in _RATINGS  # deterministic fallback, no crash


def test_llm_judge_with_mock_llm_is_robust():
    # MockLLM replies with opinion-shaped JSON (no "rating"), so llm_judge
    # detects off-schema output and falls back deterministically.
    v = LlmJudgePolicy(llm=MockLLM()).decide("NVDA", _opinions())
    assert isinstance(v, Verdict)
    assert v.rating in _RATINGS
