.PHONY: demo screen test gen-demo-data install-live help

PY ?= python3

help:
	@echo "AlphaAgent — make targets"
	@echo "  make demo           Run the offline demo pipeline (zero keys, zero network, zero install)"
	@echo "  make screen CONFIG=configs/default.toml   Run against a config"
	@echo "  make test           Run the test suite (needs: pip install pytest)"
	@echo "  make gen-demo-data  Regenerate the synthetic demo snapshots"
	@echo "  make install-live   Install optional live-data deps (yfinance)"

demo:
	$(PY) -m alphaagent demo

screen:
	$(PY) -m alphaagent screen --config $(CONFIG)

test:
	$(PY) -m pytest -q

gen-demo-data:
	$(PY) scripts/gen_demo_data.py

install-live:
	$(PY) -m pip install -e ".[live]"
