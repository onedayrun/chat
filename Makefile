# OneDay.run Platform - Makefile

.PHONY: help install dev test e2e coverage lint format run docker-up docker-bg docker-down stop logs clean

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
	pytest tests/ -v

# Run end-to-end tests (requires running app)
e2e:
	docker-compose exec -T app env E2E_BASE_URL=http://localhost:8000 pytest tests/ -v -m e2e

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
	python -m dotenv run -- uvicorn src.main:app --reload --host 0.0.0.0 --port $${APP_HOST_PORT:-8000}

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
