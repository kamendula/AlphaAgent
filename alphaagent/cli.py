"""AlphaAgent command-line entry point.

Subcommands:
  demo    Run the full offline pipeline on bundled snapshots (zero keys/network).
  screen  Run the pipeline against a config of your choice.

Kept on argparse (stdlib) so the demo path installs nothing.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from alphaagent.core.config import load_config
from alphaagent.core.env import load_dotenv
from alphaagent.core.pipeline import Pipeline
from alphaagent.report import render_backtest, render_result

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_CONFIG = _REPO_ROOT / "configs" / "demo.toml"


def _run(config_path: Path, as_of: date | None, title: str) -> int:
    config = load_config(config_path)
    pipeline = Pipeline.from_config(config)
    result = pipeline.run(as_of=as_of)
    print(render_result(result, title=title))
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    return _run(_DEMO_CONFIG, _parse_as_of(args.as_of), "AlphaAgent — demo (offline)")


def _cmd_screen(args: argparse.Namespace) -> int:
    return _run(Path(args.config), _parse_as_of(args.as_of), "AlphaAgent — screen")


def _cmd_backtest(args: argparse.Namespace) -> int:
    # Imported here so screen/demo don't pay the backtest import cost.
    from alphaagent.backtest import backtest_adapters
    from alphaagent.core.models import AssetType
    from alphaagent.data.router import SymbolRouter
    from alphaagent.entry import entry_rules

    config = load_config(Path(args.config))
    pref_raw = (config.get("data", {}) or {}).get("providers", {}) or {}
    preference = {
        AssetType(k): list(v) for k, v in pref_raw.items() if k in {a.value for a in AssetType}
    }
    router = SymbolRouter(preference=preference)

    ec = dict(config.get("entry", {}) or {})
    rule = entry_rules.get(ec.pop("rule", "breakout"))(**ec)
    bc = dict(config.get("backtest", {}) or {})
    adapter = backtest_adapters.get(bc.pop("adapter", "simple"))()

    series = router.get_prices(args.symbol)
    result = adapter.run(series, rule, bc)
    print(render_backtest(result))
    return 0


def _parse_as_of(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="alphaagent", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="run the offline demo pipeline")
    p_demo.add_argument("--as-of", help="point-in-time date YYYY-MM-DD", default=None)
    p_demo.set_defaults(func=_cmd_demo)

    p_screen = sub.add_parser("screen", help="run the pipeline against a config")
    p_screen.add_argument("--config", required=True, help="path to a .toml config")
    p_screen.add_argument("--as-of", help="point-in-time date YYYY-MM-DD", default=None)
    p_screen.set_defaults(func=_cmd_screen)

    p_bt = sub.add_parser("backtest", help="mechanical backtest of an entry rule (no agent)")
    p_bt.add_argument("--config", required=True, help="path to a .toml config with [entry]/[backtest]")
    p_bt.add_argument("--symbol", required=True, help="symbol to backtest, e.g. NVDA")
    p_bt.set_defaults(func=_cmd_backtest)

    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()  # pick up API keys from .env if present
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
