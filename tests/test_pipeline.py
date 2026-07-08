from datetime import date

from alphaagent.core.config import load_config
from alphaagent.core.pipeline import Pipeline

DEMO_CONFIG = "configs/demo.toml"


def test_demo_pipeline_produces_scored_rows():
    pipeline = Pipeline.from_config(load_config(DEMO_CONFIG))
    result = pipeline.run()
    rows = result.scored
    assert rows, "demo pipeline should return candidates"
    # sorted highest-first
    assert rows == sorted(rows, key=lambda r: r.score, reverse=True)
    for r in rows:
        assert 0.0 <= r.score <= 1.0
        assert r.factors  # each row explains its score


def test_demo_pipeline_runs_agent_panel_offline():
    # demo.toml enables the mock agent panel -> verdicts, no keys/network.
    pipeline = Pipeline.from_config(load_config(DEMO_CONFIG))
    result = pipeline.run()
    assert result.verdicts, "agent panel should produce verdicts"
    top = result.verdicts[0]
    assert top.rating in {"strong_buy", "buy", "watch", "avoid"}
    # every configured role weighed in
    assert {op.role for op in top.opinions} == {
        "fundamental",
        "technical",
        "sentiment",
        "risk",
    }


def test_as_of_truncates_history():
    pipeline = Pipeline.from_config(load_config(DEMO_CONFIG))
    early = pipeline.router.get_prices("AAPL", as_of=date(2024, 6, 1))
    assert early.last.d <= date(2024, 6, 1)
    # no bar may post-date as_of (PriceSeries enforces this too)
    assert all(b.d <= date(2024, 6, 1) for b in early.bars)


def test_resonance_merges_source_tags():
    # Two watchlists overlapping on NVDA -> two source tags on the merged candidate.
    config = {
        "data": {"providers": {"equity": ["demo"], "crypto": ["demo"]}},
        "pool": [
            {"source": "watchlist", "tag": "list-a", "symbols": ["NVDA", "AAPL"]},
            {"source": "watchlist", "tag": "list-b", "symbols": ["NVDA"]},
        ],
        "filter": {"source": "trend", "min_score": 0.0},
    }
    pipeline = Pipeline.from_config(config)
    nvda = next(c for c in pipeline.gather() if c.symbol == "NVDA")
    assert set(nvda.source_tags) == {"list-a", "list-b"}
