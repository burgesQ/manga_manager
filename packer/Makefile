# Makefile for packer developer convenience

include ../targets/help.mk

.PHONY: test
test: ## Test the packer python package. //testing
	uv run pytest -q

.PHONY: test-coverage
test-coverage: ## Run tests & show coverage in terminal. //testing
	uv run pytest --cov=packer --cov-report=term-missing

.PHONY: coverage-html
coverage-html: ## Generate HTML coverage report (htmlcov/). //testing
	uv run pytest --cov=packer --cov-report=html
