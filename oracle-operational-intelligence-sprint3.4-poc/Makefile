.PHONY: up down logs test lint seed
up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	docker compose run --rm api pytest -q

seed:
	docker compose exec api python -m app.db.seed
