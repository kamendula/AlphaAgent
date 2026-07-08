# Examples

Reference implementations of each extension point. Copy one, rename it, and you
have a working plugin.

- [`custom_provider.py`](custom_provider.py) — a minimal `DataProvider` that
  serves synthetic data, showing the `@providers.register` pattern and the
  point-in-time contract.
- [`custom_pool.py`](custom_pool.py) — a minimal `PoolSource` that returns a
  hardcoded candidate list via `@pool_sources.register`.
- [`custom_filter.py`](custom_filter.py) — a minimal `QuantFilter` that scores
  candidates on one factor (60-day momentum) through the router, via
  `@filters.register`.
- [`custom_analyst.py`](custom_analyst.py) — a minimal `Analyst` that builds
  evidence and calls `ask_opinion`, running offline with the MockLLM, via
  `@analysts.register`.

Each file is standalone-runnable (`python examples/<name>.py`).
