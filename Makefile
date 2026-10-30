ifneq (,$(wildcard .env))
include .env
export
endif

.PHONY: up down migrate test lint format shell-db

up:
	docker compose up --build -d

down:
	docker compose down

migrate:
	docker compose exec app alembic upgrade head

test:
	pytest --cov=app --cov-report=term-missing --cov-fail-under=70

lint:
	ruff check app tests
	black --check app tests
	isort --check-only app tests

format:
	ruff check --fix app tests
	black app tests
	isort app tests

shell-db:
	docker compose exec db psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)
