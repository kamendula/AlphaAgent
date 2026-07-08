"""The EntryRule contract and its registry.

Entry rules are the *timing* gate of the pipeline: given a symbol that already
cleared the (mechanical) selection chain, they decide *when* — if at all — to
enter. Like quant filters they are pure, deterministic, and agent-free by
design: the same rule that fires in a live run is exactly what the backtester
replays bar by bar.

Adding a rule is *one file + one line*::

    from alphaagent.entry.base import EntryRule, entry_rules

    @entry_rules.register("myrule")
    class MyRule(EntryRule):
        def signal(self, symbol, router, *, as_of=None):
            ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

from alphaagent.core.models import EntrySignal
from alphaagent.core.registry import Registry
from alphaagent.data.router import SymbolRouter

entry_rules: Registry[type["EntryRule"]] = Registry("entry-rule")


class EntryRule(ABC):
    """Turns a symbol's price history into a rule-based timing decision.

    Implementations pull whatever prices they need through ``router`` (so they
    stay source-agnostic and point-in-time correct) and return an
    :class:`~alphaagent.core.models.EntrySignal` with an ``action`` of
    ``buy`` / ``wait`` / ``pass``.

    The same :meth:`signal` logic is reused by the backtester, which feeds it a
    truncated series bar by bar via a tiny in-memory router (see
    :mod:`alphaagent.backtest.simple`). Keep it a pure function of the bars
    ending at ``as_of``.
    """

    def __init__(self, **config: Any) -> None:
        self.config = config

    @abstractmethod
    def signal(
        self,
        symbol: str,
        router: SymbolRouter,
        *,
        as_of: date | None = None,
    ) -> EntrySignal:
        """Return an :class:`EntrySignal` for ``symbol`` as of ``as_of``."""
