.PHONY: help install install-all install-dev install-full \
       test test-cov lint fmt check \
       infra-up infra-down infra-logs \
       migrate migrate-new migrate-down \
       clean build publish \
       docs docs-serve \
       pipeline

# ─── Help ─────────────────────────────────────────────────────────────
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Install ──────────────────────────────────────────────────────────
install: ## Install core dependencies
	pdm install

install-dev: ## Install with dev dependencies
	pdm install -G dev

install-all: ## Install everything (dev + all optional deps)
	pdm install -G dev -G full

install-full: install-all ## Alias for install-all

# ─── Testing ──────────────────────────────────────────────────────────
test: ## Run all tests
	pdm run pytest tests/ -v --tb=short

test-cov: ## Run tests with coverage report
	pdm run pytest tests/ -v --tb=short --cov=pyfetcher --cov-report=term-missing --cov-report=html

test-fast: ## Run tests without slow markers
	pdm run pytest tests/ -v --tb=short -x -q

# ─── Linting & Formatting ────────────────────────────────────────────
fmt: ## Format code with ruff
	pdm run ruff format src/ tests/ examples/

lint: ## Lint code with ruff
	pdm run ruff check src/ tests/ examples/

check: fmt lint test ## Format, lint, and test (full CI check)

ruff-fix: ## Run ruff with auto-fix
	pdm run ruff check src/ tests/ --fix

# ─── Infrastructure ──────────────────────────────────────────────────
infra-up: ## Start Postgres + MinIO via Docker Compose
	docker compose -f infra/docker-compose.yml up -d

infra-down: ## Stop infrastructure services
	docker compose -f infra/docker-compose.yml down

infra-logs: ## Tail infrastructure logs
	docker compose -f infra/docker-compose.yml logs -f

infra-reset: ## Stop and remove volumes (fresh start)
	docker compose -f infra/docker-compose.yml down -v

# ─── Database Migrations ─────────────────────────────────────────────
migrate: ## Run all pending migrations
	cd infra/alembic && alembic upgrade head

migrate-new: ## Create a new migration (usage: make migrate-new MSG="add foo table")
	cd infra/alembic && alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Rollback one migration
	cd infra/alembic && alembic downgrade -1

migrate-history: ## Show migration history
	cd infra/alembic && alembic history

# ─── Pipeline ─────────────────────────────────────────────────────────
pipeline: ## Run the crawl->scrape->download pipeline
	pdm run python -c "import asyncio; from pyfetcher.pipeline.runner import PipelineRunner; asyncio.run(PipelineRunner().start())"

# ─── Build & Publish ─────────────────────────────────────────────────
build: ## Build source and wheel distributions
	pdm build

publish: build ## Build and publish to PyPI
	pdm publish

# ─── MCP Server ────────────────────────────────────────────────────────
mcp: ## Run MCP server (stdio transport)
	pdm run python -m pyfetcher.mcp

mcp-http: ## Run MCP server (HTTP on port 8000)
	pdm run python -m pyfetcher.mcp --http 8000

mcp-list: ## List available MCP tools and resources
	pdm run fastmcp list src/pyfetcher/mcp/server.py

clean: ## Remove build artifacts and caches
	rm -rf dist/ build/ .pytest_cache/ htmlcov/ .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

# ─── Documentation ────────────────────────────────────────────────────
docs: ## Build Sphinx documentation
	pdm run sphinx-build -b html docs/ docs/_build/html

docs-serve: docs ## Build and serve docs locally
	python -m http.server -d docs/_build/html 8080

# ─── CLI ──────────────────────────────────────────────────────────────
cli-help: ## Show pyfetcher CLI help
	pdm run pyfetcher --help

tui: ## Launch the interactive TUI
	pdm run pyfetcher-tui
