include targets/help.mk

.PHONY: test
test: ## Run the full test suite. //testing
	uv run pytest . -q

.PHONY: test-coverage
test-coverage: ## Run tests with coverage report in terminal. //testing
	uv run pytest --cov=packer --cov=convertor --cov=editor --cov=manga_gui --cov-report=term-missing . -q

.PHONY: coverage-html
coverage-html: ## Generate HTML coverage report (htmlcov/). //testing
	uv run pytest --cov=packer --cov=convertor --cov=editor --cov=manga_gui --cov-report=html . -q

.PHONY: lint
lint: ## Check lint, format, and import order (read-only). //lint
	uv run ruff check .
	uv run black --check --diff .
	uv run isort --profile black --check-only .

.PHONY: lint-fix
lint-fix: ## Apply ruff, black, and isort auto-fixes. //lint
	uv run ruff check --fix .
	uv run black .
	uv run isort --profile black .

.PHONY: type-check
type-check: ## Run mypy on packer (strict) and manga_gui. //lint
	cd packer && uv run mypy --package packer
	cd gui && uv run mypy --package manga_gui

.PHONY: gui
gui: ## Start the manga-gui web UI on the host. //run
	uv run manga-gui
