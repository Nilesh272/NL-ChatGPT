.PHONY: eval eval-quick eval-internal test install install-eval check-secrets

install:
	pip install -e ".[dev]"

install-eval:
	pip install -e ".[dev,eval]"

test:
	pytest tests/ -v

# Full eval (25 items) — requires LLM + Tavily keys for best results
eval:
	python -m eval.run_all

# Fast subset without external metric libs
eval-quick:
	python -m eval.run_all --limit 5 --skip-ragas --skip-deepeval

# Internal metrics only (same as eval-quick)
eval-internal: eval-quick

# Phase 6: scan git-tracked files for leaked API keys
check-secrets:
	python scripts/check_secrets.py
