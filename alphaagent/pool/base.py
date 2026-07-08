"""The PoolSource contract and its registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from alphaagent.core.models import Candidate
from alphaagent.core.registry import Registry

pool_sources: Registry[type["PoolSource"]] = Registry("pool-source")


class PoolSource(ABC):
    """Produces a candidate universe.

    Implementations are constructed from a plain config ``dict`` (whatever the
    YAML under ``pool:`` carries) so new sources need no wiring beyond
    ``@pool_sources.register``.
    """

    def __init__(self, **config: Any) -> None:
        self.config = config

    @abstractmethod
    def fetch(self) -> list[Candidate]:
        """Return the candidate list this source proposes."""
