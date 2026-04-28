PYTHON ?= python3
SRC_DIR := src
TEST_DIR := tests
RUFF ?= $(shell command -v ruff 2>/dev/null || command -v /opt/homebrew/bin/ruff 2>/dev/null)
PYTHONPATH := $(SRC_DIR):.
export PYTHONPATH

.PHONY: help install dev model-download model-repair serve benchmark test test-unit test-e2e test-real benchmark-real lint fmt clean build ci

help: ## Show available make targets
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_-]+:.*## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install runtime and development dependencies
	$(PYTHON) -m pip install -e ".[dev]"

dev: serve ## Start the local OpenAI-compatible server

model-download: ## Download the configured Gemma 4 model
	$(PYTHON) scripts/download_model.py

model-repair: ## Repair local model config metadata for the selected profile
	$(PYTHON) scripts/repair_model_config.py

serve: ## Start the local OpenAI-compatible MLX server
	$(PYTHON) scripts/serve_openai.py

benchmark: ## Run benchmark against the configured local server
	$(PYTHON) scripts/benchmark_model.py

test: test-unit test-e2e ## Run unit and mocked e2e tests

test-unit: ## Run unit tests
	$(PYTHON) -m unittest discover -s $(TEST_DIR)/unit -p "test_*.py" -v

test-e2e: ## Run mocked e2e tests without downloading the real model
	$(PYTHON) -m unittest discover -s $(TEST_DIR)/e2e -p "test_*.py" -v

test-real: model-download ## Run real local model smoke tests
	RUN_REAL_MODEL_TESTS=1 $(PYTHON) scripts/real_smoke.py

benchmark-real: model-download ## Run the full benchmark against the real local model server
	$(PYTHON) scripts/benchmark_model.py --output-dir reports/benchmarks --label real

lint: ## Run syntax checks and ruff when available
	$(PYTHON) -m compileall -q $(SRC_DIR) scripts $(TEST_DIR)
	@if [ -n "$(RUFF)" ]; then "$(RUFF)" check $(SRC_DIR) scripts $(TEST_DIR); else echo "ruff not installed; compileall passed"; fi

fmt: ## Format code when ruff is available
	@if [ -n "$(RUFF)" ]; then "$(RUFF)" format $(SRC_DIR) scripts $(TEST_DIR); else echo "ruff not installed; skipping format"; fi

clean: ## Remove generated caches and reports
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .ruff_cache .coverage htmlcov build dist *.egg-info
	rm -f reports/benchmarks/*.json reports/benchmarks/*.md

build: lint test ## Validate source and tests

ci: lint test ## Run CI-style checks
