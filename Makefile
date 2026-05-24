.PHONY: up down ps logs api

up:
	docker compose -f infra/compose/docker-compose.yml --env-file infra/compose/.env up -d --build

down:
	docker compose -f infra/compose/docker-compose.yml --env-file infra/compose/.env down

ps:
	docker compose -f infra/compose/docker-compose.yml --env-file infra/compose/.env ps

logs:
	docker compose -f infra/compose/docker-compose.yml --env-file infra/compose/.env logs -f --tail=200

api:
	docker compose -f infra/compose/docker-compose.yml --env-file infra/compose/.env up -d --build api

