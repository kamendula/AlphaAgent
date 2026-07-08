"""The multi-agent layer: specialist analysts + a collaboration policy, run by a
swappable orchestrator.
"""

from __future__ import annotations

from typing import Any

from alphaagent.agents.base import (
    Analyst,
    AnalystContext,
    CollaborationPolicy,
    analysts,
    collaboration_policies,
)
from alphaagent.agents.orchestrator import Orchestrator, orchestrators
from alphaagent.llm.base import LLMClient, llms

# Import subpackages/modules for their registration side effects.
from alphaagent.agents import roles as _roles  # noqa: F401,E402
from alphaagent.agents import policies as _policies  # noqa: F401,E402
import alphaagent.llm as _llm  # noqa: F401,E402

__all__ = [
    "Analyst",
    "AnalystContext",
    "CollaborationPolicy",
    "Orchestrator",
    "analysts",
    "collaboration_policies",
    "orchestrators",
    "build_llm",
    "build_orchestrator",
    "DEFAULT_ROLES",
]

DEFAULT_ROLES = ["fundamental", "technical", "sentiment", "risk"]


def build_llm(cfg: dict[str, Any]) -> LLMClient:
    """Construct the configured LLM client (defaults to the offline mock)."""

    name = cfg.get("llm", "mock")
    kwargs = {k: v for k, v in cfg.items() if k in {"model", "base_url"}}
    return llms.get(name)(**kwargs)


def build_orchestrator(cfg: dict[str, Any]) -> Orchestrator:
    """Build an orchestrator (analysts + policy) from an ``[agents]`` config."""

    role_names = cfg.get("roles", DEFAULT_ROLES)
    analyst_list = [analysts.get(r)() for r in role_names]

    # Some policies (e.g. llm_judge) take an llm; most don't. Try with, fall back
    # without — keeps the builder agnostic to individual policy signatures.
    policy_cls = collaboration_policies.get(cfg.get("policy", "panel"))
    try:
        policy = policy_cls(llm=build_llm(cfg))
    except TypeError:
        policy = policy_cls()

    name = cfg.get("orchestrator", "simple")
    max_workers = int(cfg.get("max_workers", 4))
    return orchestrators.get(name)(analyst_list, policy, max_workers=max_workers)
