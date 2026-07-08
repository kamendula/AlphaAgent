"""Plain-text rendering of pipeline output. No dependencies, terminal-friendly."""

from __future__ import annotations

from alphaagent.core.models import ScoredTable, Verdict
from alphaagent.core.pipeline import PipelineResult


def render_table(rows: ScoredTable, *, title: str = "AlphaAgent — screen") -> str:
    lines: list[str] = [title, "=" * len(title)]
    if not rows:
        lines.append("(no candidates cleared the filter)")
        return "\n".join(lines)

    header = f"{'#':>2}  {'SYMBOL':<10} {'TYPE':<7} {'SCORE':>6}  {'FACTORS':<44} SOURCES"
    lines.append(header)
    lines.append("-" * len(header))
    for i, r in enumerate(rows, 1):
        factors = " ".join(f"{k}={v:.2f}" for k, v in r.factors.items())
        lines.append(
            f"{i:>2}  {r.symbol:<10} {r.asset_type.value:<7} {r.score:>6.3f}  "
            f"{factors:<44} {','.join(r.source_tags)}"
        )
    return "\n".join(lines)


def render_verdicts(verdicts: list[Verdict]) -> str:
    lines: list[str] = ["", "Agent panel verdicts", "--------------------"]
    for v in verdicts:
        lines.append(f"\n{v.symbol}  ->  {v.rating.upper()}  (confidence {v.confidence:.2f})")
        for op in v.opinions:
            lines.append(
                f"    · {op.role:<12} {op.stance:<9} conf={op.confidence:.2f} "
                f"[{op.info_richness}]  {op.rationale}"
            )
        if v.key_risks:
            lines.append(f"    ! risks: {'; '.join(v.key_risks)}")
    return "\n".join(lines)


def render_signals(signals: list) -> str:
    lines: list[str] = ["", "Entry signals (rule-based, no agent)", "-----------------------------------"]
    for s in signals:
        trig = f"trigger={s.trigger_price:.2f}" if s.trigger_price else "trigger=-"
        stop = f"stop={s.stop_hint:.2f}" if s.stop_hint else "stop=-"
        lines.append(f"    {s.symbol:<10} {s.action.upper():<5} {trig:<18} {stop:<14} {s.rationale}")
    return "\n".join(lines)


def render_result(result: PipelineResult, *, title: str = "AlphaAgent — screen") -> str:
    out = render_table(result.scored, title=title)
    n = len(result.scored)
    if result.verdicts:
        out += "\n" + render_verdicts(result.verdicts)
    if result.signals:
        out += "\n" + render_signals(result.signals)

    if result.probe is not None:
        flag = "contaminated" if getattr(result.probe, "contaminated", False) else "clean"
        out += (
            f"\n\n🛡️  PIT-Guard: leakage probe {getattr(result.probe, 'score', 0.0):.2f} ({flag}); "
            "agent tools bounded to as-of, evidence-grounded."
        )

    if result.verdicts:
        out += (
            f"\n\n{n} candidate(s) passed the mechanical filter; "
            f"{len(result.verdicts)} sent to the agent panel."
        )
    else:
        out += (
            f"\n\n{n} candidate(s) passed. Scores are mechanical only — no agent involved."
        )
    return out


def render_backtest(result) -> str:
    """Render a BacktestResult (duck-typed) for the `alphaagent backtest` command."""

    title = f"AlphaAgent — backtest: {result.symbol}"
    lines = [title, "=" * len(title)]
    lines.append(
        f"trades={result.num_trades}  win_rate={result.win_rate:.0%}  "
        f"expectancy={result.expectancy:+.2f}R  "
        f"avg_win={result.avg_win_R:+.2f}R  avg_loss={result.avg_loss_R:+.2f}R"
    )
    if result.trades:
        lines.append("")
        lines.append(f"    {'ENTRY':<12} {'EXIT':<12} {'R':>6}  REASON")
        lines.append("    " + "-" * 40)
        for t in result.trades:
            lines.append(
                f"    {str(t.entry_date):<12} {str(t.exit_date):<12} {t.r:>6.2f}  {t.reason}"
            )
    lines.append("")
    lines.append("Mechanical edge only — the agent layer is bypassed in backtests by design.")
    return "\n".join(lines)
