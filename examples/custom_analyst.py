"""Reference plugin: a custom Analyst in ~25 lines.

An analyst gathers evidence for a symbol and asks the LLM for one structured
:class:`Opinion`. The heavy lifting (prompt building + reply parsing) lives in
``ask_opinion`` — a role just assembles its evidence dict. This one is a simple
momentum-flavoured take. To make it live, move it under
``alphaagent/agents/roles/`` and import it from that package's ``__init__``
(and optionally add a ``prompts/<role>.md`` persona file).

Run this file directly (offline: MockLLM + demo provider) to see it work::

    python examples/custom_analyst.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the repo importable when this file is run directly (python examples/...).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alphaagent.agents.base import Analyst, AnalystContext, analysts  # noqa: E402
from alphaagent.agents.prompting import ask_opinion  # noqa: E402
from alphaagent.core.indicators import roc, sma  # noqa: E402
from alphaagent.core.models import Opinion  # noqa: E402


@analysts.register("example_analyst")
class ExampleAnalyst(Analyst):
    role = "technical"  # reuse the "technical" persona/handler offline

    def analyze(self, symbol: str, ctx: AnalystContext) -> Opinion:
        series = ctx.router.get_prices(symbol, as_of=ctx.as_of)
        closes = series.closes
        ma = sma(closes, 50)
        evidence = {
            "close": round(closes[-1], 2),
            "above_sma50": bool(ma and closes[-1] > ma),
            "momentum_60d": round(roc(closes, 60) or 0.0, 4),
        }
        # persona is omitted -> loaded from prompts/<role>.md automatically.
        return ask_opinion(ctx, self.role, symbol, evidence)


if __name__ == "__main__":
    from datetime import date

    import alphaagent.data.providers.demo  # noqa: F401 - registers "demo"
    from alphaagent.core.models import AssetType
    from alphaagent.data.router import SymbolRouter
    from alphaagent.llm.mock import MockLLM

    router = SymbolRouter(
        preference={AssetType.EQUITY: ["demo"], AssetType.CRYPTO: ["demo"]}
    )
    ctx = AnalystContext(router=router, llm=MockLLM(), as_of=date(2024, 12, 31))
    op = analysts.get("example_analyst")().analyze("NVDA", ctx)
    print(f"example_analyst -> {op.stance} (confidence {op.confidence:.2f})")
    print(f"  rationale: {op.rationale}")
