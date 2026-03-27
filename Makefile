.PHONY: lint typecheck lint-frontend format check-all sync-shared

sync-shared:
	cp services/shared/logging_config.py services/agent/logging_config.py
	cp services/shared/logging_config.py services/mcp_servers/wildlife_sightings/logging_config.py
	cp services/shared/logging_config.py services/mcp_servers/conservation_docs/logging_config.py
	cp services/shared/logging_config.py services/mcp_servers/weather/logging_config.py

lint:
	ruff check . --fix
	ruff format .

typecheck:
	mypy models/ services/ infra/ --strict

lint-frontend:
	cd frontend && npx eslint --ext .ts,.tsx src/
	cd frontend && npx prettier --check src/

format:
	ruff format .
	cd frontend && npx prettier --write src/

check-all: sync-shared lint typecheck lint-frontend
	@echo "All checks passed"
