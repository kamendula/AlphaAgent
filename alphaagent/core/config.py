"""Configuration loading.

Configs are TOML (parsed by the stdlib ``tomllib`` on Python 3.11+), so the demo
path needs no third-party YAML library. See ``configs/demo.toml`` for the shape.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def load_config(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"config not found: {p}")
    with p.open("rb") as fh:
        return tomllib.load(fh)
