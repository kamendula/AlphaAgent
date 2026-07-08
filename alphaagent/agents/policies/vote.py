"""``vote`` collaboration policy: one confidence-weighted ballot per analyst.

A deliberately *simpler* aggregator than ``panel``. Where the panel judge blends
stances into a continuous net score (also weighting by info richness), ``vote``
runs a plain election: each opinion casts a ballot for its stance, weighted only
by the analyst's confidence, and the stance with the most weight wins. The
winning bucket's total weight (relative to all ballots) sets the rating tier —
a landslide bullish result rates higher than a narrow one.

This keeps the strategy easy to reason about ("the room voted, bulls won by a
mile") and gives contributors a clean second policy to study next to ``panel``.
"""

from __future__ import annotations

from alphaagent.agents.base import CollaborationPolicy, collaboration_policies
from alphaagent.core.models import Opinion, Verdict

# Which camp each stance votes with. cautious rides with bearish here (a "vote"
# is coarse by design — that's the point of contrast with panel's fine grading).
_CAMP = {
    "bullish": "bull",
    "neutral": "neutral",
    "cautious": "bear",
    "bearish": "bear",
}


@collaboration_policies.register("vote")
class VotePolicy(CollaborationPolicy):
    def decide(self, symbol: str, opinions: list[Opinion]) -> Verdict:
        if not opinions:
            return Verdict(symbol=symbol, rating="watch", confidence=0.0)

        # Tally confidence-weighted ballots per camp.
        tally: dict[str, float] = {"bull": 0.0, "neutral": 0.0, "bear": 0.0}
        total = 0.0
        for op in opinions:
            camp = _CAMP.get(op.stance, "neutral")
            weight = max(0.0, op.confidence)
            tally[camp] += weight
            total += weight

        # Winning camp; ties break toward caution (neutral over bull/bear).
        winner = max(tally, key=lambda c: (tally[c], c == "neutral"))
        margin = tally[winner] / total if total else 0.0

        # Confidence in the verdict = the winner's share of the vote.
        confidence = round(margin, 2)

        support = [
            f"{op.role}: {op.rationale}"
            for op in opinions
            if _CAMP.get(op.stance) == winner and op.rationale
        ]
        risks: list[str] = []
        refs: list[str] = []
        for op in opinions:
            for r in op.key_risks:
                if r not in risks:
                    risks.append(r)
            for ref in op.evidence_refs:
                if ref not in refs:
                    refs.append(ref)

        return Verdict(
            symbol=symbol,
            rating=_rating(winner, margin),
            confidence=confidence,
            key_support=support,
            key_risks=risks,
            evidence_refs=refs,
            opinions=opinions,
        )


def _rating(winner: str, margin: float) -> str:
    """Map the winning camp + its share of the vote to a rating tier."""

    if winner == "bull":
        return "strong_buy" if margin >= 0.66 else "buy"
    if winner == "bear":
        return "avoid"
    return "watch"  # neutral won, or no decisive camp
