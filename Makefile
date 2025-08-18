VENV_DIR = $(HOME)/.venv/git-crossref

.PHONY: help lint test clean venv

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

lint: ## Run linting checks
	tox -e lint, format, typecheck

test: ## Run tests
	tox -e test

clean: ## Clean up build artifacts and cache
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .tox/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

venv:
	python3 -m venv $(VENV_DIR) && \
	$(VENV)/python3 -m pip install --upgrade pip && \
	$(VENV)/python3 -m pip install -r docker/requirements.txt
