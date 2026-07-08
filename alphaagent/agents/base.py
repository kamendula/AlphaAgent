"""Agent-layer contracts: analysts, collaboration policies, and their context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

from alphaagent.core.models import Opinion, Verdict
from alphaagent.core.registry import Registry
from alphaagent.data.router import SymbolRouter
from alphaagent.llm.base import LLMClient

analysts: Registry[type["Analyst"]] = Registry("analyst")
# Named to avoid clashing with the `policies/` subpackage as an attribute.
collaboration_policies: Registry[type["CollaborationPolicy"]] = Registry("collaboration-policy")


@dataclass
class AnalystContext:
    """Everything an analyst needs to do its job.

    ``as_of`` and ``anonymize`` are the hooks the PIT-Guard (M3) will enforce:
    data is fetched point-in-time, and identity can be masked before it reaches
    the LLM.
    """

    router: SymbolRouter
    llm: LLMClient
    as_of: date | None = None
    anonymize: bool = False
    # When set, opinions are passed through PIT-Guard's evidence-grounding check.
    enforce_grounding: bool = False


class Analyst(ABC):
    """A specialist that forms one structured :class:`Opinion` on a symbol."""

    #: Stable role name (also the registry key). Set on each subclass.
    role: str = "generic"

    @abstractmethod
    def analyze(self, symbol: str, ctx: AnalystContext) -> Opinion:
        ...


class CollaborationPolicy(ABC):
    """Aggregates a set of opinions into a single :class:`Verdict`.

    The policy is *pure aggregation* — running the analysts is the orchestrator's
    job. That keeps ``panel`` (this milestone) trivial while leaving room for
    richer policies (debate, vote) later.
    """

    @abstractmethod
    def decide(self, symbol: str, opinions: list[Opinion]) -> Verdict:
        ...
