# Makefile for packer developer convenience

include ../targets/help.mk

.PHONY: test test-coverage coverage-html

# Run the test suite
test: ## Test the packer python package. //testing
	uv run pytest -q

# Run tests and show coverage in terminal
test-coverage: ## Run tests & show coverage in terminal. //testing
	uv run pytest --cov=packer --cov-report=term-missing

# Generate an HTML coverage report (output in htmlcov/)
coverage-html: ## Generate HTML coverage report (htmlcov/). //testing
