.PHONY: install test clean run help

help:
	@echo "MAJ Document Recognition - Makefile"
	@echo ""
	@echo "Available commands:"
	@echo "  make install       Install package in development mode"
	@echo "  make install-dev   Install with development dependencies"
	@echo "  make test          Run all tests"
	@echo "  make test-cov      Run tests with coverage report"
	@echo "  make lint          Run code linting"
	@echo "  make format        Format code with black"
	@echo "  make clean         Clean build artifacts"
	@echo "  make run           Run web GUI"
	@echo "  make docs          Generate documentation"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	pytest

test-cov:
	pytest --cov=src --cov-report=html --cov-report=term

lint:
	flake8 src tests
	mypy src

format:
	black src tests examples
	isort src tests examples

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

run:
	python -m src.web.app

docs:
	@echo "Documentation is in docs/ directory"
	@echo "Open docs/README.md for full documentation"

.DEFAULT_GOAL := help
