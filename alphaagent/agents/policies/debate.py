"""``debate`` collaboration policy: bull-vs-bear adversarial adjudication.

``debate`` (multi-round bull/bear argument -> judge) is an optional collaboration
topology that separates the argument structure from the convergence gate. Where
``panel`` blends every opinion into one net score, ``debate`` first *splits the
room into two camps* — bulls vs. the bears/skeptics — then adjudicates the
strongest case from each side. It's a distinct CollaborationPolicy, not just
parameter-tuning on panel.

The design mirrors ``llm_judge`` for its two honesty constraints:

* **Offline-safe.** ``llm`` is an *optional* constructor argument defaulting to
  ``None``. ``build_orchestrator`` constructs policies as ``policy_cls(llm=...)``
  with a ``TypeError`` fallback, so accepting the kwarg lets an LLM be wired in
  later while the no-LLM path drives a fully DETERMINISTIC adjudication today —
  the offline/mock demo never needs a network.
* **Robust to junk.** LLMs emit prose, code fences, trailing commentary. We grab
  the first ``{...}`` block and coerce every field; anything unparseable or
  off-schema falls back to the deterministic adjudication rather than raising.
"""

from __future__ import annotations

import json
import re

from alphaagent.agents.base import CollaborationPolicy, collaboration_policies
from alphaagent.core.models import Opinion, Verdict
from alphaagent.llm.base import LLMClient

_RATINGS = ("strong_buy", "buy", "watch", "avoid")

# Which camp each stance argues for. cautious sides with the bears (a skeptic is
# arguing against the bull thesis) — consistent with vote.py's coarse camps.
_CAMP = {
    "bullish": "bull",
    "neutral": "neutral",
    "cautious": "bear",
    "bearish": "bear",
}

# Reuse panel.py's info-richness weighting so a confident-but-evidence-poor
# analyst does not out-shout a well-grounded one.
_RICHNESS_WEIGHT = {"A": 1.0, "B": 0.8, "C": 0.3}

_SCHEMA = (
    'Return ONLY a JSON object with keys: '
    '"rating" (strong_buy|buy|watch|avoid), '
    '"confidence" (0..1), '
    '"key_support" (list of strings), '
    '"key_risks" (list of strings).'
)

# Same tolerant JSON grab used by llm_judge.py / agents/prompting.py: first
# {...} block wins. Copied locally so we never import prompting.py internals.
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


@collaboration_policies.register("debate")
class DebatePolicy(CollaborationPolicy):
    """Adjudicates a bull-vs-bear debate into a verdict, with a safe fallback.

    Parameters
    ----------
    llm:
        The chat client that presides over the debate. If ``None`` (the default,
        and what the current no-arg orchestrator construction produces), the
        policy degrades gracefully to a deterministic confidence-weighted
        adjudication of bull strength vs. bear strength.
    rounds:
        How many debate rounds the LLM is asked to weigh. Purely a prompt hint;
        the deterministic path ignores it (its adjudication is single-shot).
    """

    def __init__(self, llm: LLMClient | None = None, rounds: int = 1) -> None:
        self.llm = llm
        self.rounds = max(1, int(rounds))

    def decide(self, symbol: str, opinions: list[Opinion]) -> Verdict:
        if not opinions:
            return Verdict(symbol=symbol, rating="watch", confidence=0.0)

        bulls = [op for op in opinions if _CAMP.get(op.stance) == "bull"]
        bears = [op for op in opinions if _CAMP.get(op.stance) == "bear"]

        # No LLM available -> deterministic adjudication (offline demo path).
        if self.llm is None:
            return self._adjudicate(symbol, opinions, bulls, bears)

        system = (
            "You preside over an adversarial equity-research debate. One camp of "
            "analysts argues the bull case; another argues the bear/risk case. "
            f"Weigh the strongest bull argument against the strongest bear "
            f"argument over {self.rounds} round(s). Trust confident, "
            "evidence-rich takes over hand-wavy ones, and take the bear case "
            "seriously rather than splitting the difference. Ground your call in "
            f"what the analysts actually said.\n{_SCHEMA}"
        )
        user = _build_prompt(symbol, bulls, bears)

        try:
            raw = self.llm.chat(system, user)
        except Exception:  # noqa: BLE001 - never let a flaky LLM break the run
            return self._adjudicate(symbol, opinions, bulls, bears)

        parsed = _parse(raw)
        if parsed is None:
            # Unparseable / off-schema output -> deterministic adjudication.
            return self._adjudicate(symbol, opinions, bulls, bears)

        rating, confidence, support, judge_risks = parsed

        # Union the judge's risks with those the analysts raised, so nothing a
        # specialist flagged silently vanishes.
        risks = list(judge_risks)
        for op in opinions:
            for r in op.key_risks:
                if r not in risks:
                    risks.append(r)
        refs = _collect_refs(opinions)

        return Verdict(
            symbol=symbol,
            rating=rating,
            confidence=confidence,
            key_support=support,
            key_risks=risks,
            evidence_refs=refs,
            opinions=opinions,
        )

    # ----------------------------------------------------------------------- #
    # Deterministic path (offline / fallback)
    # ----------------------------------------------------------------------- #
    def _adjudicate(
        self,
        symbol: str,
        opinions: list[Opinion],
        bulls: list[Opinion],
        bears: list[Opinion],
    ) -> Verdict:
        """Compare confidence-weighted bull strength vs. bear strength.

        Each camp's strength is the sum of ``confidence * richness_weight`` over
        its members — so the debate is won by the side with the stronger,
        better-evidenced case, not merely the louder one. The net edge maps to a
        rating with the same threshold style as panel.py.
        """

        bull_strength = _camp_strength(bulls)
        bear_strength = _camp_strength(bears)
        total = bull_strength + bear_strength

        # Net edge in [-1, 1]: +1 all-bull, -1 all-bear, 0 balanced/empty camps.
        net = (bull_strength - bear_strength) / total if total else 0.0
        # Confidence = how decisive the debate was (margin of victory).
        confidence = round(abs(net), 2)

        # Support = the winning camp's grounded arguments; if bears win (or it's
        # a wash), lead with the bull theses that were rebutted so the reader
        # sees what was argued.
        winners = bulls if net >= 0 else bears
        support = [f"{op.role}: {op.rationale}" for op in winners if op.rationale]

        risks: list[str] = []
        for op in opinions:
            for r in op.key_risks:
                if r not in risks:
                    risks.append(r)
        refs = _collect_refs(opinions)

        return Verdict(
            symbol=symbol,
            rating=_rating(net),
            confidence=confidence,
            key_support=support,
            key_risks=risks,
            evidence_refs=refs,
            opinions=opinions,
        )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _camp_strength(camp: list[Opinion]) -> float:
    """Confidence-weighted, richness-discounted strength of a camp's case."""

    return sum(
        op.confidence * _RICHNESS_WEIGHT.get(op.info_richness, 0.3) for op in camp
    )


def _collect_refs(opinions: list[Opinion]) -> list[str]:
    refs: list[str] = []
    for op in opinions:
        for ref in op.evidence_refs:
            if ref not in refs:
                refs.append(ref)
    return refs


def _rating(net: float) -> str:
    """Map the bull-minus-bear edge to a rating (panel.py's threshold style)."""

    if net >= 0.5:
        return "strong_buy"
    if net >= 0.15:
        return "buy"
    if net > -0.15:
        return "watch"
    return "avoid"


def _build_prompt(symbol: str, bulls: list[Opinion], bears: list[Opinion]) -> str:
    """Render the two camps into a compact, machine-and-human-readable prompt."""

    def _fmt(op: Opinion) -> str:
        risks = "; ".join(op.key_risks) if op.key_risks else "none"
        return (
            f"- role={op.role} stance={op.stance} confidence={op.confidence:.2f} "
            f"info_richness={op.info_richness} | {op.rationale or '(no rationale)'} "
            f"| risks: {risks}"
        )

    lines = [f"SYMBOL: {symbol}", "BULL CAMP:"]
    lines.extend(_fmt(op) for op in bulls) if bulls else lines.append("- (empty)")
    lines.append("BEAR CAMP:")
    lines.extend(_fmt(op) for op in bears) if bears else lines.append("- (empty)")
    lines.append("Adjudicate the debate and return the JSON verdict.")
    return "\n".join(lines)


def _parse(raw: str) -> tuple[str, float, list[str], list[str]] | None:
    """Extract (rating, confidence, key_support, key_risks) or ``None`` on junk."""

    match = _JSON_RE.search(raw or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    rating = str(data.get("rating", "")).strip().lower()
    if rating not in _RATINGS:
        return None  # off-schema rating -> let the caller fall back

    confidence = _clip_float(data.get("confidence", 0.5))
    support = [str(x) for x in _as_list(data.get("key_support")) if x]
    risks = [str(x) for x in _as_list(data.get("key_risks")) if x]
    return rating, confidence, support, risks


def _as_list(x: object) -> list:
    if isinstance(x, list):
        return x
    if x in (None, ""):
        return []
    return [x]


def _clip_float(x: object, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        return round(max(lo, min(hi, float(x))), 2)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return lo
