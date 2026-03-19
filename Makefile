.PHONY: lint typecheck lint-frontend format check-all

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

check-all: lint typecheck lint-frontend
	@echo "All checks passed"
