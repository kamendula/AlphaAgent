"""AlphaAgent — asset-agnostic, multi-agent stock & crypto screening framework.

Pipeline: pluggable pool sources -> mechanical quant filter -> multi-agent
panel -> rule-based entry timing, with a point-in-time guard over the agent
layer. The whole chain runs fully offline via `make demo`.
"""

__version__ = "0.1.0"
