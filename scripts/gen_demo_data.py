"""Generate deterministic synthetic OHLCV snapshots for the offline demo.

Committed output lives in ``demo_data/<SYMBOL>.csv``. Data is fully synthetic
(a seeded random walk with per-symbol drift) so the demo is reproducible and
carries no licensing concerns. Re-run with::

    python scripts/gen_demo_data.py
"""

from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "demo_data"
END = date(2024, 12, 31)
N_BARS = 300

# symbol -> (seed, daily_drift, daily_vol, start_price)
# Drift is tuned to dominate noise over N_BARS so trends read clearly in the demo.
SPECS = {
    "AAPL": (11, 0.0012, 0.010, 150.0),    # steady uptrend
    "MSFT": (22, 0.0010, 0.010, 320.0),    # steady uptrend
    "NVDA": (33, 0.0035, 0.018, 45.0),     # strong momentum -> should top the list
    "AMZN": (44, -0.0015, 0.012, 190.0),   # downtrend -> should score low / drop out
    "BTC-USD": (55, 0.0022, 0.022, 42000.0),  # volatile uptrend
    "ETH-USD": (66, 0.0002, 0.028, 2300.0),   # choppy / roughly flat
}


def _weekday_dates(end: date, n: int) -> list[date]:
    days: list[date] = []
    d = end
    while len(days) < n:
        if d.weekday() < 5:  # Mon-Fri
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


def _gen(seed: int, drift: float, vol: float, start: float, dates: list[date]):
    rng = random.Random(seed)
    price = start
    for d in dates:
        ret = drift + rng.gauss(0, vol)
        prev = price
        price = max(0.01, price * (1 + ret))
        high = max(prev, price) * (1 + abs(rng.gauss(0, vol / 2)))
        low = min(prev, price) * (1 - abs(rng.gauss(0, vol / 2)))
        volume = round(rng.uniform(0.8, 1.3) * 1_000_000)
        yield d, round(prev, 2), round(high, 2), round(low, 2), round(price, 2), volume


# Synthetic fundamentals for the equity symbols (crypto has none, by design).
# eps_growth is newest-first YoY per quarter; a descending sequence == accelerating.
FUNDAMENTALS = {
    "AAPL": {"eps_growth": [0.12, 0.09, 0.07, 0.05], "revenue_growth": 0.08,
             "net_margin": 0.25, "pe": 30.0},
    "MSFT": {"eps_growth": [0.10, 0.10, 0.09, 0.09], "revenue_growth": 0.12,
             "net_margin": 0.35, "pe": 33.0},
    "NVDA": {"eps_growth": [0.35, 0.28, 0.20, 0.15], "revenue_growth": 0.50,
             "net_margin": 0.50, "pe": 45.0},
    "AMZN": {"eps_growth": [-0.05, -0.02, 0.01, 0.03], "revenue_growth": -0.01,
             "net_margin": 0.05, "pe": 40.0},
}


# Synthetic recent headlines per equity (dates before the price-data END).
# Tone is chosen to broadly match each name's fundamentals story.
NEWS = {
    "AAPL": [
        ("2024-12-18", "Analysts raise targets as services revenue beats expectations", "up"),
        ("2024-12-05", "Strong holiday demand signals for flagship devices", "up"),
        ("2024-11-20", "Supply chain checks point to steady production", "neutral"),
    ],
    "MSFT": [
        ("2024-12-15", "Cloud growth steady; AI copilot adoption expands", "up"),
        ("2024-11-28", "Enterprise spending outlook described as resilient", "neutral"),
    ],
    "NVDA": [
        ("2024-12-20", "Data-center GPU demand described as insatiable by partners", "up"),
        ("2024-12-10", "New accelerator ramp ahead of schedule, suppliers say", "up"),
        ("2024-11-25", "Record backlog reported as AI buildout accelerates", "up"),
    ],
    "AMZN": [
        ("2024-12-16", "Margin pressure concerns weigh on retail outlook", "down"),
        ("2024-12-02", "Softer guidance disappoints as costs rise", "down"),
        ("2024-11-22", "Logistics investment questioned by some analysts", "down"),
    ],
}


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    dates = _weekday_dates(END, N_BARS)
    for symbol, (seed, drift, vol, start) in SPECS.items():
        path = OUT_DIR / f"{symbol}.csv"
        with path.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["date", "open", "high", "low", "close", "volume"])
            for d, o, h, lo, c, v in _gen(seed, drift, vol, start, dates):
                w.writerow([d.isoformat(), o, h, lo, c, v])
        print(f"wrote {path.relative_to(OUT_DIR.parent)} ({N_BARS} bars)")

    fdir = OUT_DIR / "fundamentals"
    fdir.mkdir(exist_ok=True)
    for symbol, f in FUNDAMENTALS.items():
        record = {
            "symbol": symbol,
            "latest_period": "2024-09-30",
            "latest_filing": "2024-11-01",  # filed before the price-data END
            **f,
        }
        (fdir / f"{symbol}.json").write_text(json.dumps(record, indent=2))
        print(f"wrote demo_data/fundamentals/{symbol}.json")

    ndir = OUT_DIR / "news"
    ndir.mkdir(exist_ok=True)
    for symbol, headlines in NEWS.items():
        records = [
            {"date": d, "title": title, "site": "demo-wire", "summary": tone}
            for d, title, tone in headlines
        ]
        (ndir / f"{symbol}.json").write_text(json.dumps(records, indent=2))
        print(f"wrote demo_data/news/{symbol}.json")


if __name__ == "__main__":
    main()
