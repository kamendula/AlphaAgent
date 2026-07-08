"""Entry rules: the mechanical *timing* gate (no LLM, by design).

An entry rule looks at a symbol's price history and decides when — if at all —
to enter, emitting an :class:`~alphaagent.core.models.EntrySignal`. It is the
second of two independent gates: the AI selection chain says *what*, the rule
chain says *when*, and only the mechanical layer is ever backtested.
"""

from alphaagent.entry.base import EntryRule, entry_rules

# Register built-ins.
from alphaagent.entry import rules as _rules  # noqa: F401

__all__ = ["EntryRule", "entry_rules"]
