"""Shared prompt construction + reply parsing for analysts.

One place builds the (system, user) prompt and parses the JSON reply into an
:class:`Opinion`, so every role stays a few lines. The ``EVIDENCE_JSON`` line is
both human-readable and the machine hook the MockLLM reads offline.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from alphaagent.agents.base import AnalystContext
from alphaagent.core.models import Opinion

_SCHEMA = (
    'Return ONLY a JSON object with keys: '
    '"stance" (bullish|neutral|cautious|bearish), '
    '"confidence" (0..1), "rationale" (one sentence), '
    '"key_risks" (list of strings), "evidence_refs" (list of strings), '
    '"info_richness" (A|B|C — how much real evidence you had).'
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

# Editable persona files live next to this module in ``prompts/<role>.md`` so
# non-coders can tune agent behaviour without touching Python.
_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@lru_cache(maxsize=None)
def load_persona(role: str) -> str:
    """Return the editable persona text for ``role`` from ``prompts/<role>.md``.

    Results are cached. If the file is missing (e.g. ``prompts/`` wasn't packaged
    as package-data), we fall back to a sensible generic persona so the package
    keeps working rather than crashing.
    """

    path = _PROMPTS_DIR / f"{role}.md"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        text = ""
    return text or f"You are a {role} analyst; reason only from the evidence provided."


def ask_opinion(
    ctx: AnalystContext,
    role: str,
    symbol: str,
    evidence: dict,
    persona: str | None = None,
) -> Opinion:
    """Prompt the LLM for a structured opinion and parse it (robust to junk).

    ``persona`` is optional: when ``None`` it is loaded from the editable
    ``prompts/<role>.md`` file via :func:`load_persona`.
    """

    if persona is None:
        persona = load_persona(role)

    # PIT-Guard anti-leakage: mask identity so the model reasons over evidence,
    # not recognition ("NVDA which I know 10x'd"). See pitguard/anonymize.py.
    if ctx.anonymize:
        from alphaagent.agents.pitguard.anonymize import pseudonymize, scrub_evidence

        label = pseudonymize(symbol)
        evidence = scrub_evidence(evidence, symbol)
    else:
        label = symbol

    system = (
        f"You are a {role} analyst. {persona}\n"
        "Be decisive but honest about uncertainty; ground every claim in the "
        f"evidence provided — do not rely on outside recall.\n{_SCHEMA}"
    )
    user = (
        f"ROLE: {role}\n"
        f"SYMBOL: {label}\n"
        "Assess this security from your specialty and return the JSON.\n"
        f"EVIDENCE_JSON: {json.dumps(evidence)}"
    )

    raw = ctx.llm.chat(system, user)
    return _parse(role, raw)


def _parse(role: str, raw: str) -> Opinion:
    data: dict = {}
    match = _JSON_RE.search(raw or "")
    if match:
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            data = {}

    return Opinion(
        role=role,
        stance=str(data.get("stance", "neutral")).lower(),
        confidence=_clip_float(data.get("confidence", 0.3)),
        rationale=str(data.get("rationale", "")),
        key_risks=[str(x) for x in data.get("key_risks", []) if x],
        evidence_refs=[str(x) for x in data.get("evidence_refs", []) if x],
        info_richness=str(data.get("info_richness", "C")).upper()[:1] or "C",
    )


def _clip_float(x: object, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        return max(lo, min(hi, float(x)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return lo
