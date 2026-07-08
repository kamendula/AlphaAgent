"""PIT-Guard — the point-in-time / anti-leakage middleware.

Keeps the agent layer honest about *when* it is. Leakage has two sources and
this package tackles both:

* **Tool/data boundary** (deterministic, ~90% of leakage) —
  :class:`GuardedRouter` / :func:`wrap_router` force ``as_of`` on every fetch and
  re-validate that no bar post-dates it (:class:`PITViolation`).
* **Parametric memory** (compressed, not deletable) —
  :func:`pseudonymize` / :func:`scrub_text` strip identity before the LLM sees
  it; :func:`enforce_grounding` penalises claims not backed by controlled
  evidence; :func:`leakage_probe` measures residual contamination.

Everything is opt-in via the ``AnalystContext`` hooks (``as_of`` / ``anonymize``)
so the default demo path is unchanged.
"""

from __future__ import annotations

from alphaagent.agents.pitguard.anonymize import (
    pseudonymize,
    scrub_evidence,
    scrub_text,
)
from alphaagent.agents.pitguard.boundary import (
    GuardedRouter,
    PITViolation,
    wrap_router,
)
from alphaagent.agents.pitguard.evidence import enforce_grounding
from alphaagent.agents.pitguard.probe import ProbeResult, leakage_probe

__all__ = [
    "GuardedRouter",
    "wrap_router",
    "PITViolation",
    "pseudonymize",
    "scrub_text",
    "scrub_evidence",
    "enforce_grounding",
    "leakage_probe",
    "ProbeResult",
]
