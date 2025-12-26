# OneDay.run Platform - Makefile

.PHONY: help install dev test e2e e2e-ui playwright-install build publish publish-test coverage lint format run docker-up docker-bg docker-down docker-health docker-wait stop logs clean

PYTHON ?= python3

# Default target
help:
	@echo "OneDay.run Platform - Available commands:"
	@echo ""
	@echo "  make install    - Install dependencies"
	@echo "  make dev        - Install dev dependencies"
	@echo "  make test       - Run tests"
	@echo "  make coverage   - Run tests with coverage"
	@echo "  make lint       - Run linters"
	@echo "  make format     - Format code"
	@echo "  make run        - Run development server"
	@echo "  make docker     - Build and run with Docker"
	@echo "  make clean      - Clean build artifacts"

# Install production dependencies
install:
	pip install -r requirements.txt

# Install development dependencies
dev:
	pip install -e ".[dev]"

# Run tests
test:
	pytest tests/ -v -m "not e2e and not e2e_ui"

# Run end-to-end tests (requires running app)
e2e:
	docker-compose up -d app
	$(MAKE) docker-wait
	docker-compose exec -T app env E2E_BASE_URL=http://localhost:8000 pytest tests/ -v -m e2e

playwright-install:
	$(PYTHON) -m playwright install chromium

e2e-ui:
	$(PYTHON) -m dotenv run -- bash -c 'PORT="$${APP_PORT:-$${APP_HOST_PORT:-8000}}"; E2E_BASE_URL="http://localhost:$${PORT}" pytest tests/ -v -m e2e_ui'

# Run tests with coverage
coverage:
	pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
	@echo "Coverage report: htmlcov/index.html"

# Run linters
lint:
	ruff check src/ tests/
	mypy src/

# Format code
format:
	black src/ tests/
	ruff check --fix src/ tests/

# Run development server
run:
	$(PYTHON) -m dotenv run -- bash -c 'uvicorn src.main:app --reload --host "$${APP_HOST:-0.0.0.0}" --port "$${APP_PORT:-$${APP_HOST_PORT:-8000}}"'

# Build and run with Docker
docker-up:
	docker-compose up --build -d
	$(MAKE) docker-wait

# Docker in background
docker-bg:
	$(MAKE) docker-up

# Stop Docker
docker-down:
	docker-compose down

# Alias: stop
stop: docker-down

# View logs
logs:
	docker-compose logs -f

docker-health:
	@for svc in app db redis litellm; do \
	  cid=$$(docker-compose ps -q $$svc 2>/dev/null); \
	  if [ -z "$$cid" ]; then \
	    echo "$$svc: not running"; \
	  else \
	    status=$$(docker inspect -f '{{.State.Status}}' $$cid 2>/dev/null || echo unknown); \
	    health=$$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' $$cid 2>/dev/null || echo none); \
	    echo "$$svc: $$status (health=$$health)"; \
	  fi; \
	done

docker-wait:
	@set -e; \
	services="db redis app"; \
	if docker-compose ps -q litellm >/dev/null 2>&1 && [ -n "$$(docker-compose ps -q litellm)" ]; then services="$$services litellm"; fi; \
	for svc in $$services; do \
	  echo "Waiting for $$svc to be healthy..."; \
	  for i in $$(seq 1 60); do \
	    cid=$$(docker-compose ps -q $$svc 2>/dev/null); \
	    if [ -z "$$cid" ]; then sleep 1; continue; fi; \
	    health=$$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' $$cid 2>/dev/null || echo none); \
	    if [ "$$health" = "healthy" ]; then echo "$$svc: healthy"; break; fi; \
	    if [ $$i -eq 60 ]; then echo "$$svc: not healthy (health=$$health)"; exit 1; fi; \
	    sleep 1; \
	  done; \
	done; \
	$(MAKE) docker-health

# Clean build artifacts
clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .coverage htmlcov dist build *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

build:
	$(PYTHON) -c "import build" >/dev/null 2>&1 || (echo "Missing dependency: build. Run: make dev" >&2; exit 1)
	$(PYTHON) -m build

publish: build
	$(PYTHON) -c "import twine" >/dev/null 2>&1 || (echo "Missing dependency: twine. Run: make dev" >&2; exit 1)
	$(PYTHON) -m twine upload dist/*

publish-test: build
	$(PYTHON) -c "import twine" >/dev/null 2>&1 || (echo "Missing dependency: twine. Run: make dev" >&2; exit 1)
	$(PYTHON) -m twine upload --repository testpypi dist/*

# Database migrations (if using Alembic)
migrate:
	alembic upgrade head

# Create new migration
migration:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

# Type checking
typecheck:
	mypy src/ --ignore-missing-imports

# Security check
security:
	pip-audit

# Generate requirements.txt from pyproject.toml
requirements:
	pip-compile pyproject.toml -o requirements.txt

# Full CI check
ci: lint typecheck test
	@echo "All CI checks passed!"
