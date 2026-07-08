"""The QuantFilter contract and its registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

from alphaagent.core.models import Candidate, ScoredTable
from alphaagent.core.registry import Registry
from alphaagent.data.router import SymbolRouter

filters: Registry[type["QuantFilter"]] = Registry("quant-filter")


class QuantFilter(ABC):
    """Scores candidates using only objective, reproducible rules.

    Implementations pull whatever data they need through ``router`` (so they stay
    source-agnostic and point-in-time correct) and return a
    :data:`~alphaagent.core.models.ScoredTable` sorted highest-score-first.
    """

    def __init__(self, **config: Any) -> None:
        self.config = config

    @abstractmethod
    def score(
        self,
        candidates: list[Candidate],
        router: SymbolRouter,
        *,
        as_of: date | None = None,
    ) -> ScoredTable:
        """Return scored rows for ``candidates`` (order: best first)."""
