"""Leakage probe — PIT-Guard's residual-contamination diagnostic.

A third mitigation for parametric memory: even after anonymisation and
grounding, a model's weights may still "know the future". The probe measures the
*residual*: it directly asks the model what happens after ``as_of`` and scores
how much it volunteers.

This is a **diagnostic, not a filter** — it doesn't block a run, it quantifies
how trustworthy a point-in-time evaluation is. On :class:`~alphaagent.llm.mock.MockLLM`
(no world knowledge, only reflects the prompt's evidence) it returns ~0, which is
exactly the "clean" baseline we want the offline demo to show.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from alphaagent.llm.base import LLMClient

#: Words that betray forward-looking knowledge in a probe reply.
_TELLS = (
    "actually",
    "in reality",
    "went on to",
    "later",
    "subsequently",
    "as we now know",
    "turned out",
    "the price rose",
    "the price fell",
    "rallied",
    "crashed",
    "surged",
    "plunged",
)

#: Phrases a well-behaved model uses to *refuse* — these should lower the score.
_REFUSALS = (
    "i cannot know",
    "i don't know",
    "i do not know",
    "no way to know",
    "cannot predict",
    "beyond my knowledge",
    "as of",
    "point-in-time",
)


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """Outcome of a single leakage probe."""

    as_of: date
    score: float  # 0.0 (clean) .. 1.0 (blatant future knowledge)
    contaminated: bool  # score above the flag threshold
    reply: str  # raw model reply, for auditing


def leakage_probe(
    llm: LLMClient, as_of: date, *, threshold: float = 0.34
) -> ProbeResult:
    """Ask the model about the future and score how much it leaks.

    The score is a transparent lexical heuristic: fraction of "tell" phrases that
    appear, netted down when the reply explicitly refuses. It is intentionally
    simple and auditable — a smoke test for contamination, not a guarantee.
    """

    system = (
        "You are being tested for point-in-time discipline. You must not use any "
        f"knowledge dated after {as_of.isoformat()}. If asked about the future, "
        "refuse and say you cannot know."
    )
    user = (
        f"It is {as_of.isoformat()}. Tell me exactly what happens to the market "
        "in the days and weeks AFTER this date — name the moves you already know."
    )

    reply = llm.chat(system, user) or ""
    low = reply.lower()

    tells = sum(1 for phrase in _TELLS if phrase in low)
    refused = any(phrase in low for phrase in _REFUSALS)

    # Normalise tell-count into 0..1, then discount a clear refusal.
    raw = min(1.0, tells / 3.0)
    score = 0.0 if refused else raw
    score = round(score, 2)

    return ProbeResult(
        as_of=as_of,
        score=score,
        contaminated=score >= threshold,
        reply=reply,
    )
