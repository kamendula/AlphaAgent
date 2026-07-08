"""``llm_judge`` collaboration policy: an LLM synthesizes the verdict.

Instead of a deterministic formula, this policy hands the analysts' opinions to
an :class:`~alphaagent.llm.base.LLMClient` and asks it to reason out a single
:class:`Verdict` — the "judge" half of the panel+judge topology in its
LLM-native form.

Two honesty constraints shape the design:

* **Offline-safe.** ``CollaborationPolicy.decide`` is called with no ``llm``
  today (see ``build_orchestrator``), and the no-arg construction in
  ``build_orchestrator`` cannot pass one in yet. So ``llm`` is an *optional*
  constructor argument that defaults to ``None``; with no LLM we fall back to
  the deterministic panel aggregation and never crash. Wiring an LLM in is an
  opt-in upgrade (see integration notes), not a requirement.
* **Robust to junk.** LLMs emit prose, code fences, trailing commentary. We
  extract the first JSON object from the reply and coerce/clip every field;
  anything unparseable falls back to the deterministic verdict rather than
  raising.
"""

from __future__ import annotations

import json
import re

from alphaagent.agents.base import CollaborationPolicy, collaboration_policies
from alphaagent.agents.policies.panel import PanelPolicy
from alphaagent.core.models import Opinion, Verdict
from alphaagent.llm.base import LLMClient

_RATINGS = ("strong_buy", "buy", "watch", "avoid")

_SCHEMA = (
    'Return ONLY a JSON object with keys: '
    '"rating" (strong_buy|buy|watch|avoid), '
    '"confidence" (0..1), '
    '"key_support" (list of strings), '
    '"key_risks" (list of strings).'
)

# Same tolerant JSON grab used by agents/prompting.py: first {...} block wins.
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


@collaboration_policies.register("llm_judge")
class LlmJudgePolicy(CollaborationPolicy):
    """Synthesizes opinions into a verdict via an LLM, with a safe fallback.

    Parameters
    ----------
    llm:
        The chat client the judge reasons with. If ``None`` (the default, and
        what the current no-arg orchestrator construction produces), the policy
        degrades gracefully to deterministic :class:`PanelPolicy` aggregation.
    """

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm
        self._fallback = PanelPolicy()

    def decide(self, symbol: str, opinions: list[Opinion]) -> Verdict:
        if not opinions:
            return Verdict(symbol=symbol, rating="watch", confidence=0.0)

        # No LLM available -> deterministic aggregation (offline demo path).
        if self.llm is None:
            return self._fallback.decide(symbol, opinions)

        system = (
            "You are the presiding judge of an equity-research panel. Several "
            "specialist analysts have each submitted a structured opinion. "
            "Weigh them against each other — trust confident, evidence-rich "
            "takes over hand-wavy ones, and take dissent (risk/bear) seriously "
            "rather than splitting the difference. Ground your call in what the "
            f"analysts actually said.\n{_SCHEMA}"
        )
        user = _build_prompt(symbol, opinions)

        try:
            raw = self.llm.chat(system, user)
        except Exception:  # noqa: BLE001 - never let a flaky LLM break the run
            return self._fallback.decide(symbol, opinions)

        parsed = _parse(raw)
        if parsed is None:
            # Unparseable / off-schema output -> deterministic fallback.
            return self._fallback.decide(symbol, opinions)

        rating, confidence, support, judge_risks = parsed

        # Union the judge's risks with those the analysts raised, so nothing
        # flagged by a specialist silently vanishes.
        risks = list(judge_risks)
        for op in opinions:
            for r in op.key_risks:
                if r not in risks:
                    risks.append(r)
        refs: list[str] = []
        for op in opinions:
            for ref in op.evidence_refs:
                if ref not in refs:
                    refs.append(ref)

        return Verdict(
            symbol=symbol,
            rating=rating,
            confidence=confidence,
            key_support=support,
            key_risks=risks,
            evidence_refs=refs,
            opinions=opinions,
        )


def _build_prompt(symbol: str, opinions: list[Opinion]) -> str:
    """Render the opinions into a compact, machine-and-human-readable prompt."""

    lines = [f"SYMBOL: {symbol}", "OPINIONS:"]
    for op in opinions:
        risks = "; ".join(op.key_risks) if op.key_risks else "none"
        lines.append(
            f"- role={op.role} stance={op.stance} confidence={op.confidence:.2f} "
            f"info_richness={op.info_richness} | {op.rationale or '(no rationale)'} "
            f"| risks: {risks}"
        )
    lines.append("Synthesize these into a single verdict and return the JSON.")
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
