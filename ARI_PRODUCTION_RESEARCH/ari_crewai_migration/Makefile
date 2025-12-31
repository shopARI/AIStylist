.PHONY: help test test-unit test-integration test-crewai test-e2e test-quick test-all coverage lint format clean install

# Default target
help:
	@echo "ARI CrewAI Migration - Makefile Commands"
	@echo "=========================================="
	@echo ""
	@echo "Testing:"
	@echo "  make test              - Run all tests"
	@echo "  make test-unit         - Run unit tests only"
	@echo "  make test-integration  - Run integration tests (pattern-based)"
	@echo "  make test-crewai       - Run CrewAI agent tests (requires API key)"
	@echo "  make test-e2e          - Run end-to-end tests"
	@echo "  make test-quick        - Quick test run (unit tests, no coverage)"
	@echo "  make coverage          - Generate coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint              - Run linters (flake8, black, isort)"
	@echo "  make format            - Auto-format code (black, isort)"
	@echo ""
	@echo "Setup:"
	@echo "  make install           - Install dependencies"
	@echo "  make install-dev       - Install dev dependencies"
	@echo "  make install-hooks     - Install pre-commit hooks"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean             - Remove generated files"
	@echo ""

# Testing targets
test:
	./run_tests.sh all

test-unit:
	./run_tests.sh unit

test-integration:
	./run_tests.sh integration

test-crewai:
	./run_tests.sh crewai

test-e2e:
	./run_tests.sh e2e

test-quick:
	./run_tests.sh quick false

test-all: test

# Coverage
coverage:
	source ../crewai_env/bin/activate && \
	python -m pytest tests/unit/ tests/integration/test_intent_detection_comprehensive.py \
		--cov=nlp --cov=crews \
		--cov-report=html \
		--cov-report=term-missing \
		--cov-report=xml
	@echo ""
	@echo "Coverage report generated:"
	@echo "  HTML: htmlcov/index.html"
	@echo "  XML: coverage.xml"

# Code quality
lint:
	source ../crewai_env/bin/activate && \
	flake8 nlp/ crews/ tests/ --count --select=E9,F63,F7,F82 --show-source --statistics && \
	flake8 nlp/ crews/ tests/ --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics && \
	black --check nlp/ crews/ tests/ && \
	isort --check-only nlp/ crews/ tests/

format:
	source ../crewai_env/bin/activate && \
	black nlp/ crews/ tests/ && \
	isort nlp/ crews/ tests/
	@echo "Code formatted!"

# Installation
install:
	source ../crewai_env/bin/activate && \
	pip install crewai>=0.203.1 python-dotenv chromadb

install-dev:
	source ../crewai_env/bin/activate && \
	pip install pytest pytest-asyncio pytest-cov && \
	pip install flake8 black isort && \
	pip install bandit safety && \
	pip install pre-commit

install-hooks:
	source ../crewai_env/bin/activate && \
	pip install pre-commit && \
	pre-commit install
	@echo "Pre-commit hooks installed!"

# Cleanup
clean:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	find . -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name 'htmlcov' -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name 'coverage.xml' -delete
	find . -type f -name '.coverage' -delete
	@echo "Cleaned up generated files!"
