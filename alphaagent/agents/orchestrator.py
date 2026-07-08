"""Orchestrator: runs analysts and applies a collaboration policy.

This is the swappable backbone. The default ``simple`` implementation is a thin,
readable runner that keeps the multi-agent logic explicit and framework-free.
Alternative orchestrator backends can register against this same interface later.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor

from alphaagent.agents.base import Analyst, AnalystContext, CollaborationPolicy
from alphaagent.core.models import Opinion, Verdict
from alphaagent.core.registry import Registry

orchestrators: Registry[type["Orchestrator"]] = Registry("orchestrator")

# Evidence refs that correspond to real, controlled tools (grows with providers).
# PIT-Guard's grounding check treats anything outside this set as ungrounded.
KNOWN_EVIDENCE_REFS = {"price:ohlcv", "fundamentals:financials", "news:headlines"}


class Orchestrator(ABC):
    @abstractmethod
    def run(self, symbols: list[str], ctx: AnalystContext) -> list[Verdict]:
        ...


@orchestrators.register("simple")
class SimpleOrchestrator(Orchestrator):
    """Per symbol: run every analyst (concurrently), then apply the policy."""

    def __init__(
        self,
        analysts: list[Analyst],
        policy: CollaborationPolicy,
        max_workers: int = 4,
    ) -> None:
        self.analysts = analysts
        self.policy = policy
        self.max_workers = max(1, max_workers)

    def _run_analyst(self, analyst: Analyst, symbol: str, ctx: AnalystContext) -> Opinion:
        try:
            opinion = analyst.analyze(symbol, ctx)
        except Exception as exc:  # noqa: BLE001 - one bad analyst shouldn't sink the panel
            return Opinion(
                role=analyst.role,
                stance="neutral",
                confidence=0.0,
                rationale=f"analyst error: {exc}",
                info_richness="C",
            )

        if ctx.enforce_grounding:
            from alphaagent.agents.pitguard.evidence import enforce_grounding

            opinion = enforce_grounding(opinion, KNOWN_EVIDENCE_REFS)
        return opinion

    def run(self, symbols: list[str], ctx: AnalystContext) -> list[Verdict]:
        verdicts: list[Verdict] = []
        for symbol in symbols:
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                # Preserve analyst order regardless of completion order.
                opinions = list(
                    pool.map(lambda a: self._run_analyst(a, symbol, ctx), self.analysts)
                )
            verdicts.append(self.policy.decide(symbol, opinions))
        return verdicts
