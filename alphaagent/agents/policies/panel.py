"""``panel`` collaboration policy: parallel specialists, weighted aggregation.

The judge here is a transparent, deterministic aggregator: each opinion is
weighted by its confidence *and* its information richness (an abstaining analyst
with poor evidence barely counts), then mapped to a rating. This keeps the demo
reproducible and the decision auditable. An LLM-judge variant can be added as a
sibling policy later.
"""

from __future__ import annotations

from alphaagent.agents.base import CollaborationPolicy, collaboration_policies
from alphaagent.core.models import Opinion, Verdict

_STANCE_VALUE = {
    "bullish": 1.0,
    "neutral": 0.0,
    "cautious": -0.4,
    "bearish": -1.0,
}
_RICHNESS_WEIGHT = {"A": 1.0, "B": 0.8, "C": 0.3}


@collaboration_policies.register("panel")
class PanelPolicy(CollaborationPolicy):
    def decide(self, symbol: str, opinions: list[Opinion]) -> Verdict:
        if not opinions:
            return Verdict(symbol=symbol, rating="watch", confidence=0.0)

        num = 0.0
        den = 0.0
        conf_num = 0.0
        for op in opinions:
            w = op.confidence * _RICHNESS_WEIGHT.get(op.info_richness, 0.3)
            num += _STANCE_VALUE.get(op.stance, 0.0) * w
            den += w
            conf_num += op.confidence * w

        net = num / den if den else 0.0
        confidence = round(conf_num / den, 2) if den else 0.0

        support = [
            f"{op.role}: {op.rationale}"
            for op in opinions
            if op.stance == "bullish" and op.rationale
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
            rating=_rating(net),
            confidence=confidence,
            key_support=support,
            key_risks=risks,
            evidence_refs=refs,
            opinions=opinions,
        )


def _rating(net: float) -> str:
    if net >= 0.5:
        return "strong_buy"
    if net >= 0.15:
        return "buy"
    if net > -0.15:
        return "watch"
    return "avoid"
