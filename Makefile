.PHONY: up down build logs ps dev dev-frontend migrate migrate-new

# ===== Docker =====
build:
	docker compose build

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

# ===== Migrations (容器内) =====
migrate:
	docker compose exec backend alembic upgrade head

migrate-new:
	@read -p "Migration message: " msg; \
	docker compose exec backend alembic revision --autogenerate -m "$$msg"

# ===== 本地开发 (不走 docker) =====
dev:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8123

dev-frontend:
	cd frontend && npm run dev

# ===== 本地迁移 =====
local-migrate:
	cd backend && .venv/bin/alembic upgrade head
