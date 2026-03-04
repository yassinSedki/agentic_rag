.PHONY: help install dev lint format test test-cov compose-up compose-down clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	poetry install --without dev

dev: ## Install with dev dependencies
	poetry install

lint: ## Run linters (ruff + mypy)
	poetry run ruff check app/ tests/
	poetry run mypy app/ --ignore-missing-imports

format: ## Auto-format code (ruff + black)
	poetry run ruff check app/ tests/ --fix
	poetry run black app/ tests/

test: ## Run unit tests (no external services needed)
	poetry run pytest tests/ -m "not integration" -v

test-cov: ## Run tests with coverage report
	poetry run pytest tests/ -m "not integration" --cov=app --cov-report=html --cov-report=term

test-integration: ## Run integration tests (requires Docker)
	docker compose -f docker-compose.test.yml up -d
	poetry run pytest tests/ -m integration -v
	docker compose -f docker-compose.test.yml down

compose-up: ## Start all services
	docker compose up -d --build

compose-down: ## Stop all services
	docker compose down

clean: ## Clean caches and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage dist/ build/ *.egg-info
