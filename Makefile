.PHONY: up down build migrate migrate-new logs ps dev dev-beat dev-worker

# ===== Docker =====
build:
	docker-compose build

up:
	docker-compose up -d --build

down:
	docker-compose down

logs:
	docker-compose logs -f

ps:
	docker-compose ps

# ===== Migrations =====
# 在 backend 容器内执行迁移
migrate:
	docker-compose exec backend alembic upgrade head

migrate-new:
	@read -p "Migration message: " msg; \
	docker-compose exec backend alembic revision --autogenerate -m "$$msg"

# ===== 本地开发 (不走 docker) =====
# 需要: 本地 pg(5433) + redis(6380) 已起, 或用 make up db redis
dev:
	cd backend && uvicorn app.main:app --reload --port 8000

dev-worker:
	cd backend && celery -A worker.celery_app.celery_app worker --loglevel=info

dev-beat:
	cd backend && celery -A worker.celery_app.celery_app beat --loglevel=info
