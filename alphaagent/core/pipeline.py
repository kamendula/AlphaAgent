"""The pipeline orchestrator.

Wires the selection chain: pool sources -> merge/resonance -> quant filter ->
(optional) multi-agent panel -> verdicts. The agent stage is opt-in via an
``[agents]`` config block; without it the pipeline behaves exactly as in M0
(mechanical only), which is also how backtests will run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from alphaagent.core.models import (
    AssetType,
    Candidate,
    EntrySignal,
    ScoredTable,
    Verdict,
)
from alphaagent.data.router import SymbolRouter
from alphaagent.filters.base import QuantFilter, filters
from alphaagent.pool.base import PoolSource, pool_sources

_ASSET_BY_NAME = {a.value: a for a in AssetType}


@dataclass
class PipelineResult:
    """What a full run produces across the two gates + PIT-Guard diagnostics."""

    scored: ScoredTable
    verdicts: list[Verdict] = field(default_factory=list)
    signals: list[EntrySignal] = field(default_factory=list)
    #: PIT-Guard leakage-probe result (set only when pit_guard is enabled).
    probe: object | None = None


@dataclass
class Pipeline:
    """A configured selection pipeline."""

    sources: list[PoolSource]
    quant_filter: QuantFilter
    router: SymbolRouter
    agents_cfg: dict[str, Any] | None = None
    entry_cfg: dict[str, Any] | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ build
    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "Pipeline":
        data_cfg = config.get("data", {}) or {}
        pref_raw = data_cfg.get("providers", {}) or {}
        preference = {
            _ASSET_BY_NAME[k]: list(v)
            for k, v in pref_raw.items()
            if k in _ASSET_BY_NAME
        }
        # `fallback = false` keeps a run to its listed providers only — the demo
        # sets this so it never touches the network (all data is offline).
        fallback = bool(data_cfg.get("fallback", True))
        router = SymbolRouter(preference=preference, fallback=fallback)

        pool_cfgs = config.get("pool", [])
        if isinstance(pool_cfgs, dict):
            pool_cfgs = [pool_cfgs]
        sources: list[PoolSource] = []
        for pc in pool_cfgs:
            pc = dict(pc)
            name = pc.pop("source")
            sources.append(pool_sources.get(name)(**pc))
        if not sources:
            raise ValueError("config has no [[pool]] sources")

        fc = dict(config.get("filter", {}) or {})
        fname = fc.pop("source", "trend")
        quant_filter = filters.get(fname)(**fc)

        agents_cfg = config.get("agents")  # None -> agent stage disabled
        entry_cfg = config.get("entry")  # None -> entry stage disabled
        return cls(
            sources=sources,
            quant_filter=quant_filter,
            router=router,
            agents_cfg=agents_cfg,
            entry_cfg=entry_cfg,
        )

    # -------------------------------------------------------------------- run
    def gather(self) -> list[Candidate]:
        """Fetch from every source and merge duplicates (union of source tags)."""

        merged: dict[str, Candidate] = {}
        for source in self.sources:
            for cand in source.fetch():
                key = cand.symbol.upper()
                if key in merged:
                    for tag in cand.source_tags:
                        if tag not in merged[key].source_tags:
                            merged[key].source_tags.append(tag)
                else:
                    merged[key] = cand
        return list(merged.values())

    def run(self, *, as_of: date | None = None) -> PipelineResult:
        """Run pool -> filter -> (optional) agent panel -> (optional) entry timing."""

        candidates = self.gather()
        scored = self.quant_filter.score(candidates, self.router, as_of=as_of)
        result = PipelineResult(scored=scored)

        if self.agents_cfg:
            self._run_agents(scored, as_of, result)

        if self.entry_cfg:
            self._run_entry(scored, as_of, result)

        return result

    def _run_agents(self, scored: ScoredTable, as_of, result: PipelineResult) -> None:
        # Import here so the mechanical path never pays the agent-layer import cost.
        from alphaagent.agents import AnalystContext, build_llm, build_orchestrator

        top_k = int(self.agents_cfg.get("top_k", 3))
        symbols = [r.symbol for r in scored[:top_k]]
        if not symbols:
            return

        pit_guard = bool(self.agents_cfg.get("pit_guard", False))
        anonymize = bool(self.agents_cfg.get("anonymize", pit_guard))

        llm = build_llm(self.agents_cfg)
        orchestrator = build_orchestrator(self.agents_cfg)

        # PIT-Guard boundary: wrap the router so no agent can see past `as_of`.
        from alphaagent.agents.pitguard import wrap_router

        ctx = AnalystContext(
            router=wrap_router(self.router, as_of),
            llm=llm,
            as_of=as_of,
            anonymize=anonymize,
            enforce_grounding=pit_guard,
        )
        result.verdicts = orchestrator.run(symbols, ctx)

        if pit_guard:
            from datetime import date as _date

            from alphaagent.agents.pitguard import leakage_probe

            result.probe = leakage_probe(llm, as_of or _date(2024, 12, 31))

    def _run_entry(self, scored: ScoredTable, as_of, result: PipelineResult) -> None:
        from alphaagent.entry import entry_rules

        ec = dict(self.entry_cfg)
        rule = entry_rules.get(ec.pop("rule", "breakout"))(**ec)
        result.signals = [
            rule.signal(r.symbol, self.router, as_of=as_of) for r in scored
        ]
