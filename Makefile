# Question Metadata Engine - common commands
.PHONY: test test-unit lint format typecheck run-api help

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-14s\033[0m %s\n", $$1, $$2}'

test:  ## Run all tests except costly AI evaluations
	pytest tests/unit tests/integration tests/failure -v

test-all:  ## Run all tests including AI evaluation (costs money)
	pytest tests -v

test-ai:  ## Run AI evaluation tests only (requires OPENAI_API_KEY, costs money)
	pytest tests/ai_evaluation -v

lint:  ## Run ruff + mypy
	ruff check src tests
	mypy

format:  ## Auto-format with ruff
	ruff format src tests
	ruff check --fix src tests

typecheck:  ## Run mypy only
	mypy

run-api:  ## Start FastAPI dev server
	uvicorn qme.main:app --reload --host 0.0.0.0 --port 8000

install:  ## Install package with dev dependencies
	pip install -e ".[dev]"
