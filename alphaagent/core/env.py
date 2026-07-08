"""Minimal ``.env`` loader (stdlib only).

Reads ``KEY=VALUE`` lines from a ``.env`` file into ``os.environ`` without
overriding variables already set in the real environment. Deliberately tiny — no
python-dotenv dependency, no interpolation, no export keyword handling.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: str | Path = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for raw in p.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
