"""Sentiment analyst — reads the recent news narrative.

Pulls a point-in-time news feed through the router (FMP live, or bundled offline
headlines), summarises a naive tone signal plus the latest headlines, and lets
the LLM judge whether the narrative is supportive, negative, or noise. Abstains
honestly when no news is available (e.g. an obscure symbol).

Note: identity anonymization is only partial for news — headlines may name the
company in prose even when the ticker is scrubbed. A fuller entity-scrub is a
future PIT-Guard enhancement.
"""

from __future__ import annotations

from alphaagent.agents.base import Analyst, AnalystContext, analysts
from alphaagent.agents.prompting import ask_opinion
from alphaagent.core.models import Opinion

_POSITIVE = {
    "beat", "beats", "strong", "record", "raise", "raised", "growth", "surge",
    "surges", "expand", "expands", "resilient", "insatiable", "ahead", "demand",
    "upgrade", "upgrades", "outperform", "tops", "rally", "boost", "wins",
}
_NEGATIVE = {
    "pressure", "disappoint", "disappoints", "soft", "softer", "cut", "cuts",
    "miss", "misses", "weak", "decline", "declines", "concern", "concerns",
    "questioned", "downgrade", "downgrades", "lawsuit", "probe", "warn", "warns",
    "slump", "fear", "fears", "loss", "losses",
}


def _tone(titles: list[str]) -> float:
    """Naive lexical tone in [-1, 1]: mean per-headline pos/neg direction."""

    if not titles:
        return 0.0
    scores = []
    for t in titles:
        words = {w.strip(".,!?:;\"'").lower() for w in t.split()}
        pos = len(words & _POSITIVE)
        neg = len(words & _NEGATIVE)
        scores.append((pos > neg) - (neg > pos))  # +1 / 0 / -1
    return sum(scores) / len(scores)


@analysts.register("sentiment")
class SentimentAnalyst(Analyst):
    role = "sentiment"

    def analyze(self, symbol: str, ctx: AnalystContext) -> Opinion:
        try:
            feed = ctx.router.get_news(symbol, as_of=ctx.as_of, limit=8)
        except Exception as exc:  # noqa: BLE001 - no provider / no news
            evidence = {"available": False, "note": f"no news ({type(exc).__name__})"}
            return ask_opinion(ctx, self.role, symbol, evidence)

        titles = [it.title for it in feed.items[:6]]
        evidence = {
            "available": True,
            "headline_count": len(feed),
            "net_tone": round(_tone(titles), 3),
            "recent_headlines": titles,
            "latest": feed.items[0].d.isoformat() if feed.items else None,
        }
        return ask_opinion(ctx, self.role, symbol, evidence)
