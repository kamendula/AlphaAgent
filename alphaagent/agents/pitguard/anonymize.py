"""Identity scrubbing — PIT-Guard's mitigation for parametric-memory leakage.

Leakage source two — parametric memory: the boundary guard cannot delete what
the model already memorised. So before evidence reaches the LLM we strip the
symbol/company name, forcing the model to reason over *given numbers* rather than
recall a specific ticker and its subsequent price action.

The mapping is deterministic (same symbol -> same pseudonym for a whole run), so
opinions stay reproducible and a post-mortem can re-identify after the fact.
"""

from __future__ import annotations

import re

#: Prefix for generated pseudonyms, e.g. ``SEC_A1`` ("security"). Kept opaque so
#: the model gets no hint of asset class.
_PREFIX = "SEC_"
_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def pseudonymize(symbol: str) -> str:
    """Map a real symbol to a stable, opaque pseudonym (e.g. ``AAPL`` -> ``SEC_H1``).

    Deterministic: the same symbol always yields the same pseudonym, but the
    label carries no recoverable identity (a fixed hash, not the ticker).
    """

    s = symbol.strip().upper()
    # A small, stable hash over the characters — no ticker info survives, yet the
    # result is fully reproducible across processes (unlike Python's salted hash).
    acc = 0
    for ch in s:
        acc = (acc * 31 + ord(ch)) & 0xFFFFFFFF
    letter = _LETTERS[(acc >> 8) % len(_LETTERS)]
    number = acc % 10
    return f"{_PREFIX}{letter}{number}"


def scrub_text(text: str, symbol: str, *, aliases: list[str] | None = None) -> str:
    """Redact the symbol (and any known aliases) from free text.

    Case-insensitive, whole-token matching, so news/rationale strings can be
    passed to the LLM without betraying the identity. Redacted spans become the
    stable pseudonym, keeping the sentence readable.
    """

    if not text:
        return text

    pseudonym = pseudonymize(symbol)
    needles = [symbol, *(aliases or [])]
    out = text
    for needle in needles:
        needle = (needle or "").strip()
        if not needle:
            continue
        # \b won't hug tickers with '-'/'.', so bound on non-word chars ourselves.
        pattern = re.compile(
            rf"(?<![\w.]){re.escape(needle)}(?![\w.])", flags=re.IGNORECASE
        )
        out = pattern.sub(pseudonym, out)
    return out


def scrub_evidence(
    evidence: dict, symbol: str, *, aliases: list[str] | None = None
) -> dict:
    """Return a copy of ``evidence`` with identity scrubbed from string values.

    Numeric features (the point of PIT-filtered evidence) pass through untouched;
    only text fields — where a name might hide — are run through :func:`scrub_text`.
    """

    cleaned: dict = {}
    for key, value in evidence.items():
        if isinstance(value, str):
            cleaned[key] = scrub_text(value, symbol, aliases=aliases)
        elif isinstance(value, list):
            cleaned[key] = [
                scrub_text(v, symbol, aliases=aliases) if isinstance(v, str) else v
                for v in value
            ]
        else:
            cleaned[key] = value
    return cleaned
