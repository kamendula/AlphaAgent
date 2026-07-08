"""A deterministic, offline mock LLM.

It powers the agent demo without any API key. Rather than emit random text, it
reads the structured ``EVIDENCE_JSON`` block the analysts embed in the prompt and
derives an evidence-grounded opinion with simple, transparent rules. This keeps
the offline demo coherent and reproducible: same evidence -> same verdict.

Real vendors get the *same* prompt and reason freely; the mock just happens to
parse the machine-readable evidence line we already include.
"""

from __future__ import annotations

import json
import re

from alphaagent.llm.base import LLMClient, llms

_ROLE_RE = re.compile(r"^ROLE:\s*(\w+)", re.MULTILINE)
_EVIDENCE_RE = re.compile(r"^EVIDENCE_JSON:\s*(\{.*\})\s*$", re.MULTILINE | re.DOTALL)


@llms.register("mock")
class MockLLM(LLMClient):
    def chat(self, system: str, user: str) -> str:
        role = (_ROLE_RE.search(user) or _ROLE_RE.search(system))
        role = role.group(1) if role else "generic"
        ev_match = _EVIDENCE_RE.search(user)
        evidence: dict = {}
        if ev_match:
            try:
                evidence = json.loads(ev_match.group(1))
            except json.JSONDecodeError:
                evidence = {}

        handler = _HANDLERS.get(role, _generic)
        return json.dumps(handler(evidence))


# --------------------------------------------------------------------------- #
# Per-role deterministic reasoning
# --------------------------------------------------------------------------- #
def _technical(ev: dict) -> dict:
    above = bool(ev.get("above_sma50"))
    mom = float(ev.get("momentum_60d") or 0.0)
    rsi = float(ev.get("rsi14") or 50.0)

    if above and mom > 0.05:
        stance, conf = "bullish", min(0.55 + mom, 0.9)
    elif not above and mom < -0.05:
        stance, conf = "bearish", min(0.55 - mom, 0.9)
    else:
        stance, conf = "neutral", 0.4

    risks = []
    if rsi >= 70:
        risks.append(f"overbought (RSI {rsi:.0f})")
    if not above:
        risks.append("trading below its 50-day average")
    return {
        "stance": stance,
        "confidence": round(conf, 2),
        "rationale": f"{'Above' if above else 'Below'} SMA50, 60d momentum {mom:+.1%}, RSI {rsi:.0f}.",
        "key_risks": risks,
        "evidence_refs": ["price:ohlcv"],
        "info_richness": "A",
    }


def _risk(ev: dict) -> dict:
    atr_pct = float(ev.get("atr_pct") or 0.0)
    mdd = float(ev.get("max_drawdown_60d") or 0.0)
    rsi = float(ev.get("rsi14") or 50.0)

    risks = []
    if atr_pct > 0.04:
        risks.append(f"high volatility (ATR {atr_pct:.1%})")
    if mdd < -0.20:
        risks.append(f"deep recent drawdown ({mdd:.0%})")
    if rsi >= 75:
        risks.append(f"extended (RSI {rsi:.0f})")

    if len(risks) >= 2:
        stance, conf = "bearish", 0.6
    elif risks:
        stance, conf = "cautious", 0.5
    else:
        stance, conf = "neutral", 0.45
    return {
        "stance": stance,
        "confidence": round(conf, 2),
        "rationale": "Risk scan: " + ("; ".join(risks) if risks else "no elevated risk flags."),
        "key_risks": risks,
        "evidence_refs": ["price:ohlcv"],
        "info_richness": "B",
    }


def _no_data(kind: str):
    def handler(ev: dict) -> dict:
        return {
            "stance": "neutral",
            "confidence": 0.2,
            "rationale": f"No {kind} data provider wired yet (offline demo); abstaining.",
            "key_risks": [],
            "evidence_refs": [],
            "info_richness": "C",
        }

    return handler


def _fundamental(ev: dict) -> dict:
    if not ev.get("available"):
        return _no_data("fundamental")(ev)

    eps = ev.get("eps_growth_recent") or []
    g0 = float(eps[0]) if eps else 0.0
    accel = bool(ev.get("eps_accelerating"))
    rev = float(ev.get("revenue_growth") or 0.0)
    pe = ev.get("pe")

    if g0 > 0 and (accel or rev > 0.10):
        stance, conf = "bullish", min(0.55 + g0, 0.85)
    elif g0 < 0 and rev < 0:
        stance, conf = "bearish", 0.6
    else:
        stance, conf = "neutral", 0.4

    risks = []
    if g0 < 0:
        risks.append(f"EPS declining YoY ({g0:+.0%})")
    if pe is not None and pe > 40:
        risks.append(f"rich valuation (PE {pe:.0f})")
    return {
        "stance": stance,
        "confidence": round(conf, 2),
        "rationale": (
            f"EPS growth {g0:+.0%} ({'accelerating' if accel else 'not accelerating'}), "
            f"revenue {rev:+.0%}, PE {pe}."
        ),
        "key_risks": risks,
        "evidence_refs": ["fundamentals:financials"],
        "info_richness": "A",
    }


def _sentiment(ev: dict) -> dict:
    if not ev.get("available"):
        return _no_data("news/sentiment")(ev)

    tone = float(ev.get("net_tone") or 0.0)
    n = int(ev.get("headline_count") or 0)
    if tone > 0.15:
        stance, conf = "bullish", min(0.45 + tone, 0.75)
    elif tone < -0.15:
        stance, conf = "bearish", min(0.45 - tone, 0.75)
    else:
        stance, conf = "neutral", 0.4

    risks = []
    if tone < 0:
        risks.append("negative news flow")
    if n < 3:
        risks.append("thin news coverage")
    return {
        "stance": stance,
        "confidence": round(conf, 2),
        "rationale": f"{n} recent headlines, net tone {tone:+.2f}.",
        "key_risks": risks,
        "evidence_refs": ["news:headlines"],
        "info_richness": "B",
    }


def _generic(ev: dict) -> dict:
    return {
        "stance": "neutral",
        "confidence": 0.3,
        "rationale": "No role-specific reasoning available.",
        "key_risks": [],
        "evidence_refs": [],
        "info_richness": "C",
    }


_HANDLERS = {
    "technical": _technical,
    "risk": _risk,
    "fundamental": _fundamental,
    "sentiment": _sentiment,
}
