.PHONY: help test test-unit test-integration test-e2e test-tools test-gateway test-agent coverage coverage-html lint format clean

# Detect Python interpreter (prefer venv-py314, then venv)
ifeq ($(wildcard venv-py314/bin/python),)
    ifeq ($(wildcard venv/bin/python),)
        PYTHON := python3
    else
        PYTHON := venv/bin/python
    endif
else
    PYTHON := venv-py314/bin/python
endif

# Default target
help:
	@echo "Hermes-Agent Testing Commands"
	@echo "============================="
	@echo ""
	@echo "Test Categories:"
	@echo "  make test           Run all unit tests (excludes integration/e2e)"
	@echo "  make test-unit      Run unit tests only"
	@echo "  make test-tools     Run tool-specific tests"
	@echo "  make test-gateway   Run gateway tests"
	@echo "  make test-agent     Run agent tests"
	@echo "  make test-cli       Run CLI tests"
	@echo "  make test-integration Run integration tests (requires API keys)"
	@echo "  make test-e2e       Run end-to-end tests"
	@echo ""
	@echo "Coverage:"
	@echo "  make coverage       Run tests with coverage report (terminal)"
	@echo "  make coverage-html  Run tests with HTML coverage report"
	@echo "  make coverage-report Show coverage report from previous run"
	@echo ""
	@echo "Specific Tests:"
	@echo "  make test-specific FILE=tests/tools/test_approval.py"
	@echo "  make test-class FILE=tests/tools/test_approval.py CLASS=TestDetectDangerousRm"
	@echo "  make test-single FILE=tests/tools/test_approval.py TEST=test_rm_rf_detected"
	@echo ""
	@echo "Other:"
	@echo "  make clean          Clean up test artifacts"

# Quick unit tests (default)
test: test-unit

# Run all unit tests (excluding integration and e2e)
test-unit:
	@echo "Running unit tests..."
	$(PYTHON) -m pytest tests/ \
		-q \
		--ignore=tests/integration \
		--ignore=tests/e2e \
		-n auto \
		--tb=short

# Run tool tests
test-tools:
	@echo "Running tool tests..."
	$(PYTHON) -m pytest tests/tools/ \
		-v \
		--tb=short

# Run gateway tests
test-gateway:
	@echo "Running gateway tests..."
	$(PYTHON) -m pytest tests/gateway/ \
		-v \
		--tb=short

# Run agent tests
test-agent:
	@echo "Running agent tests..."
	$(PYTHON) -m pytest tests/agent/ \
		-v \
		--tb=short

# Run CLI tests
test-cli:
	@echo "Running CLI tests..."
	$(PYTHON) -m pytest tests/hermes_cli/ tests/cli/ \
		-v \
		--tb=short

# Run cron tests
test-cron:
	@echo "Running cron tests..."
	$(PYTHON) -m pytest tests/cron/ \
		-v \
		--tb=short

# Run integration tests (requires API keys)
test-integration:
	@echo "Running integration tests..."
	@echo "Note: Some tests may require API keys to be set"
	$(PYTHON) -m pytest tests/integration/ \
		-v \
		--tb=short

# Run e2e tests
test-e2e:
	@echo "Running end-to-end tests..."
	$(PYTHON) -m pytest tests/e2e/ \
		-v \
		--tb=short

# Run tests with coverage (terminal output)
coverage:
	@echo "Running tests with coverage..."
	$(PYTHON) -m pytest tests/ \
		--ignore=tests/integration \
		--ignore=tests/e2e \
		-n auto \
		--tb=short \
		--cov=. \
		--cov-report=term-missing:skip-covered \
		--cov-config=.coveragerc

# Run tests with HTML coverage report
coverage-html:
	@echo "Running tests with HTML coverage report..."
	$(PYTHON) -m pytest tests/ \
		--ignore=tests/integration \
		--ignore=tests/e2e \
		-n auto \
		--tb=short \
		--cov=. \
		--cov-report=html \
		--cov-config=.coveragerc
	@echo "HTML report generated at htmlcov/index.html"
	@echo "Open with: open htmlcov/index.html"

# Show coverage report from previous run
coverage-report:
	@echo "Coverage report from previous run:"
	@$(PYTHON) -m coverage report --skip-covered 2>/dev/null || echo "No coverage data found. Run 'make coverage' first."

# Run a specific test file
test-specific:
	@if [ -z "$(FILE)" ]; then \
		echo "Usage: make test-specific FILE=path/to/test.py"; \
		exit 1; \
	fi
	$(PYTHON) -m pytest $(FILE) -v --tb=long

# Run a specific test class
test-class:
	@if [ -z "$(FILE)" ] || [ -z "$(CLASS)" ]; then \
		echo "Usage: make test-class FILE=path/to/test.py CLASS=TestClassName"; \
		exit 1; \
	fi
	$(PYTHON) -m pytest $(FILE)::$(CLASS) -v --tb=long

# Run a specific test method
test-single:
	@if [ -z "$(FILE)" ] || [ -z "$(TEST)" ]; then \
		echo "Usage: make test-single FILE=path/to/test.py TEST=test_method_name"; \
		exit 1; \
	fi
	$(PYTHON) -m pytest $(FILE)::$(TEST) -v --tb=long -s

# Run tests matching a keyword expression
test-keyword:
	@if [ -z "$(KEYWORD)" ]; then \
		echo "Usage: make test-keyword KEYWORD=dangerous"; \
		exit 1; \
	fi
	$(PYTHON) -m pytest tests/ -k "$(KEYWORD)" -v --tb=short

# Run tests with debugging output
test-debug:
	@if [ -z "$(FILE)" ]; then \
		echo "Usage: make test-debug FILE=path/to/test.py"; \
		exit 1; \
	fi
	$(PYTHON) -m pytest $(FILE) -v --tb=long -s --pdb

# Run a quick smoke test (fast tests only - minimal deps)
test-smoke:
	@echo "Running smoke tests (minimal dependencies)..."
	$(PYTHON) -m pytest \
		tests/test_example_best_practices.py \
		tests/tools/test_approval.py \
		tests/agent/test_display.py \
		-q \
		--tb=line

# Check for test coverage on new/changed files (useful in pre-commit)
test-changed:
	@echo "Running tests for changed files only..."
	@git diff --name-only HEAD | grep -E "^tests/.*\.py$$" | xargs -I {} $(PYTHON) -m pytest {} -v --tb=short 2>/dev/null || echo "No test files changed"

# Clean up test artifacts
clean:
	@echo "Cleaning up test artifacts..."
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf **/__pycache__
	rm -rf **/*.pyc
	rm -rf **/.mypy_cache
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete"

# Run all tests including integration and e2e
test-all:
	@echo "Running all tests (unit + integration + e2e)..."
	$(PYTHON) -m pytest tests/ \
		-v \
		--tb=short \
		-n auto

# Verify test setup is working
test-verify:
	@echo "Verifying test setup..."
	@$(PYTHON) -c "import pytest; print(f'pytest version: {pytest.__version__}')"
	@$(PYTHON) -c "import sys; print(f'Python version: {sys.version}')"
	@$(PYTHON) -m pytest tests/test_example_best_practices.py::TestCalculatorAdd::test_add_positive_numbers_returns_sum -v
	@echo "Test setup verified successfully!"
