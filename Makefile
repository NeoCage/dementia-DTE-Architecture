.PHONY: help install dev test lint format check demo api notebook all clean

help:
	@echo "make install  - install runtime dependencies"
	@echo "make dev      - install runtime + development dependencies (editable)"
	@echo "make test     - run the test suite"
	@echo "make lint     - lint and check formatting"
	@echo "make format   - apply formatting"
	@echo "make check    - repository health checks (labels, data safety, schemas, links)"
	@echo "make all      - lint + test + check (what CI runs)"
	@echo "make demo     - simulate a day of the Memory Anchoring Pipeline"
	@echo "make api      - start the local demo API on port 8000 (NOT for deployment)"
	@echo "make notebook - open the synthetic-cohort analysis notebook"
	@echo "make clean    - remove generated artefacts"

install:
	pip install -r requirements.txt

dev:
	pip install -r requirements-dev.txt
	pip install -e .

test:
	PYTHONPATH=src pytest -q

lint:
	ruff check src tests examples scripts
	ruff format --check src tests examples scripts

format:
	ruff format src tests examples scripts
	ruff check src tests examples scripts --fix

# Repository health checks. These guard the integrity properties described in DISCLAIMER.md and
# CONTRIBUTING.md, not just code correctness.
check:
	python scripts/check_labels.py
	python scripts/check_data_safety.py
	python scripts/check_schemas.py
	python scripts/check_links.py

all: lint test check

demo:
	PYTHONPATH=src python -m dte.cli simulate --patient-id demo-001 --hours 24 --seed 42

api:
	@echo "WARNING: no auth, no TLS, no encryption, no audit log. localhost demonstration only."
	@echo "See docs/08-security-and-privacy.md section 8.9"
	PYTHONPATH=src uvicorn dte.api.app:app --reload --port 8000

notebook:
	jupyter notebook notebooks/01_synthetic_cohort_analysis.ipynb

clean:
	rm -rf artifacts .pytest_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

# --- fidelity ladder (ADR-0010 / ADR-0011) -------------------------------------------
.PHONY: test-tiers replay-tiers

test-tiers:  ## Run the fidelity-ladder conformance suite
	PYTHONPATH=src python -m pytest tests/test_tiers.py tests/test_tier_scenarios.py -v

replay-tiers:  ## Print a human-readable trace of every tier scenario
	PYTHONPATH=src python scripts/replay_tier_scenarios.py
