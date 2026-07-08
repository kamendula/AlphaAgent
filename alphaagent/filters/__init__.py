"""Quant filters: cheap, deterministic, backtestable scoring of candidates.

A filter turns candidates into a scored table. It is the *mechanical* gate that
runs before (and instead of, during backtests) the expensive agent layer.
"""

from alphaagent.filters.base import QuantFilter, filters

# Register built-ins.
from alphaagent.filters import trend as _trend  # noqa: F401

__all__ = ["QuantFilter", "filters"]
