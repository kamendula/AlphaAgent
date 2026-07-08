# Contributing to AlphaAgent

Thanks for considering a contribution! AlphaAgent is built so that adding a
capability is **one file + one line**. Every extension point is a plugin
registered in a small `Registry`.

## Setup

```bash
git clone <repo> && cd alphaagent
make demo                 # sanity check: offline pipeline, zero install
pip install -e ".[dev]"   # for tests
make test
```

## The extension points

| You want to add… | Drop a file under… | Register with |
|---|---|---|
| A market-data source | `alphaagent/data/providers/` | `@providers.register("name")` |
| A candidate pool source | `alphaagent/pool/` | `@pool_sources.register("name")` |
| A quant filter | `alphaagent/filters/` | `@filters.register("name")` |
| An agent role *(M1)* | `alphaagent/agents/roles/` | *(coming with M1)* |
| A collaboration policy *(M1)* | `alphaagent/agents/policies/` | *(coming with M1)* |
| An entry rule *(M2)* | `alphaagent/entry/` | *(coming with M2)* |

After adding the file, import it in the package's `__init__.py` so it registers
on import (see the existing `# Register built-ins` blocks), then reference it by
name from a config.

See [`examples/`](examples/) for a complete, commented reference plugin.

## Ground rules

- **Keep the demo path dependency-free.** Anything that needs a third-party
  library must be optional and lazily imported (see `yfinance_provider.py`).
- **Respect point-in-time.** Providers must never return data dated after
  `as_of`. This is the foundation the PIT-Guard (M3) builds on.
- **Mechanical stays mechanical.** Filters and entry rules must be deterministic
  and backtestable — no LLM calls in those layers.
- Add a test under `tests/` for new logic. `make test` must stay green.

## Roadmap

See the [Roadmap in the README](README.md#-roadmap).
Good first issues will be tagged once the repo is public.
