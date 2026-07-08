"""Pool sources: pluggable producers of the candidate universe.

Each source emits :class:`~alphaagent.core.models.Candidate` objects. When the
same symbol comes from several sources, the pipeline merges them and keeps every
source tag — multi-source agreement is itself a bullish signal (resonance).
"""

from alphaagent.pool.base import PoolSource, pool_sources

# Register built-ins.
from alphaagent.pool import watchlist as _watchlist  # noqa: F401

__all__ = ["PoolSource", "pool_sources"]
