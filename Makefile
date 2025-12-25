# OneDay.run Platform - Makefile

.PHONY: help install dev test e2e e2e-ui playwright-install build publish publish-test coverage lint format run docker-up docker-bg docker-down stop logs clean

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
	docker-compose exec -T app python -c 'import time,urllib.request; exec("url=\"http://localhost:8000/health\"\nlast=None\nfor _ in range(60):\n    try:\n        urllib.request.urlopen(url, timeout=2).read(); break\n    except Exception as e:\n        last=e; time.sleep(1)\nelse:\n    raise SystemExit(\"App did not become healthy: %r\" % (last,))\n")'
	docker-compose exec -T app env E2E_BASE_URL=http://localhost:8000 pytest tests/ -v -m e2e

playwright-install:
	python -m playwright install chromium

e2e-ui:
	E2E_BASE_URL=http://localhost:$$(awk -F= '/^APP_HOST_PORT=/{print $$2}' .env | tail -n 1 | tr -d '"' | tr -d "'") pytest tests/ -v -m e2e_ui

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
	python -m dotenv run -- bash -lc 'uvicorn src.main:app --reload --host 0.0.0.0 --port $${APP_HOST_PORT:-8000}'

# Build and run with Docker
docker-up:
	docker-compose up --build -d

# Docker in background
docker-bg:
	docker-compose up --build -d

# Stop Docker
docker-down:
	docker-compose down

# Alias: stop
stop: docker-down

# View logs
logs:
	docker-compose logs -f

# Clean build artifacts
clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .coverage htmlcov dist build *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

build:
	python -c "import build" >/dev/null 2>&1 || (echo "Missing dependency: build. Run: make dev" >&2; exit 1)
	python -m build

publish: build
	python -c "import twine" >/dev/null 2>&1 || (echo "Missing dependency: twine. Run: make dev" >&2; exit 1)
	python -m twine upload dist/*

publish-test: build
	python -c "import twine" >/dev/null 2>&1 || (echo "Missing dependency: twine. Run: make dev" >&2; exit 1)
	python -m twine upload --repository testpypi dist/*

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
