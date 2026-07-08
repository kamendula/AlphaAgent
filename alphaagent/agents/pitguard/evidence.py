"""Evidence grounding — PIT-Guard's mitigation for ungrounded assertions.

A second mitigation for parametric memory: every conclusion must hang off an
``evidence_ref`` that came from a *controlled tool*. A claim with empty or
unknown refs is the model recalling, not reasoning — so we penalise it: drop the
unrecognised refs, downgrade ``info_richness`` toward ``C`` and shave confidence.

This turns recall into reasoning-over-given-evidence without silently discarding
the opinion, so the panel stays transparent.
"""

from __future__ import annotations

from dataclasses import replace

from alphaagent.core.models import Opinion

#: Confidence multiplier applied when an opinion is (partly) ungrounded.
_UNGROUNDED_PENALTY = 0.5


def enforce_grounding(opinion: Opinion, allowed_refs: set[str]) -> Opinion:
    """Downgrade an opinion whose evidence isn't grounded in the allowed refs.

    ``allowed_refs`` is the set of refs actually handed to the analyst (the keys
    of the controlled evidence). We keep only refs in that set; if that leaves
    the opinion with *no* backing, we halve confidence and force
    ``info_richness`` to ``C`` (an honest "I had nothing to stand on").

    Returns a new :class:`Opinion` (never mutates the input).
    """

    grounded = [ref for ref in opinion.evidence_refs if ref in allowed_refs]

    if grounded:
        # Fully or partly grounded: keep only the valid refs, leave the rest as-is.
        return replace(opinion, evidence_refs=grounded)

    # No grounded evidence at all -> penalise. A neutral abstention with no refs
    # is already honest, so don't punish it below its current richness.
    return replace(
        opinion,
        evidence_refs=[],
        confidence=round(opinion.confidence * _UNGROUNDED_PENALTY, 2),
        info_richness="C",
    )
