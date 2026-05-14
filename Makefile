.PHONY: help install install-dev test smoke bug check all clean dashboard run-cli backtest

PYTHON ?= python

help:
	@echo "Aegis ControlRisk OS — make targets"
	@echo ""
	@echo "  install        Install runtime dependencies"
	@echo "  install-dev    Install dev dependencies (pytest, ruff)"
	@echo "  test           Run the full pytest suite"
	@echo "  smoke          End-to-end pipeline smoke check"
	@echo "  bug            Bug regression sweep"
	@echo "  check          smoke + tests + bug (the trio CI runs)"
	@echo "  backtest       Run the synthetic backtest"
	@echo "  dashboard      Launch the Streamlit dashboard"
	@echo "  run-cli ARGS=  Run the CLI with arguments"
	@echo "                 example: make run-cli ARGS='analyze INDC'"
	@echo "  clean          Remove caches, snapshots, runtime artifacts"

install:
	$(PYTHON) -m pip install -r requirements.txt

install-dev: install
	$(PYTHON) -m pip install pytest ruff

test:
	$(PYTHON) -m pytest -q

smoke:
	$(PYTHON) smoke_test.py

bug:
	$(PYTHON) bug_test.py

check: smoke test bug
	@echo ""
	@echo "All checks passed."

backtest:
	$(PYTHON) -m aegis.backtesting.backtest_runner

dashboard:
	$(PYTHON) -m streamlit run app.py

run-cli:
	$(PYTHON) aegis_cli.py $(ARGS)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .ruff_cache snapshots .aegis_cache .aegis_workspaces
	rm -rf build dist *.egg-info
