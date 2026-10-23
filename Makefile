SHELL := /bin/bash
.DEFAULT_GOAL := help
COMPOSE := docker compose
VERSION := $(shell grep -m1 '^version' pyproject.toml | cut -d'"' -f2)

help: ## show targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up: ## boot full stack + migrate + seed
	$(COMPOSE) up --build -d
	./scripts/wait-healthy.sh
	$(COMPOSE) run --rm api python -m propulse_api.cli migrate
	$(COMPOSE) run --rm api python -m propulse_api.cli seed

dev: ## hot-reload stack
	$(COMPOSE) -f docker-compose.yml -f compose.override.yml up

down: ## stop
	$(COMPOSE) down

nuke: ## stop + wipe volumes
	$(COMPOSE) down -v

logs: ## tail logs
	$(COMPOSE) logs -f --tail=100

demo: ## end-to-end pulse demo
	$(COMPOSE) run --rm api python -m propulse_api.cli demo

test: ## unit + integration
	$(COMPOSE) run --rm api pytest -q

bench: ## record hot-path benchmark baseline
	$(COMPOSE) run --rm api pytest tests/bench -q --benchmark-autosave

lint: ## ruff + mypy + reuse + boundary
	uv run ruff format --check . && uv run ruff check .
	./scripts/typecheck.sh
	uv run reuse lint
	uv run python scripts/check_license_boundary.py
	uv run python scripts/check_env_defaults.py

fmt: ## autofix
	uv run ruff format . && uv run ruff check --fix .

openapi: ## regenerate contract
	$(COMPOSE) run --rm api python -m propulse_api.cli export-openapi > docs/openapi.json

sbom: ## emit SPDX SBOM
	$(COMPOSE) run --rm api python -m propulse_api.cli sbom > sbom.spdx.json

doctor: ## diagnostics
	$(COMPOSE) run --rm api python -m propulse_api.cli doctor

harden: ## apply repo settings
	./scripts/harden-repo.sh

docs: ## serve docs
	uv run mkdocs serve

.PHONY: help up dev down nuke logs demo test bench lint fmt openapi sbom doctor harden docs
