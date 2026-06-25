.PHONY: help install dev dev-backend dev-frontend build build-frontend migrate clean
.PHONY: deploy ship status restart logs stop tail

# 默认目标显示帮助
help:
	@echo "CronFlow Makefile — 单进程 FastAPI + SQLite + systemd 部署"
	@echo ""
	@echo "  本地开发:"
	@echo "    make install         安装后端 venv + 前端 npm 依赖"
	@echo "    make dev             起后端 (uvicorn :8123, --reload)"
	@echo "    make dev-frontend    起前端 dev server (vite :5173, proxy 到 :8123)"
	@echo "    make migrate         本地 alembic upgrade head"
	@echo ""
	@echo "  构建:"
	@echo "    make build           前端 npm run build (生成 frontend/dist)"
	@echo ""
	@echo "  部署:"
	@echo "    make ship SERVER=u@ip 一键打包前端、同步到远程(仅dist, 排除前端源码)、执行安装脚本"
	@echo "    make deploy          在目标服务器上运行 deploy/install.sh (本地部署或已同步时使用)"
	@echo ""
	@echo "  服务管理 (sudo systemctl):"
	@echo "    make status          systemctl status cronflow"
	@echo "    make restart         systemctl restart cronflow"
	@echo "    make stop            systemctl stop cronflow"
	@echo "    make tail            journalctl -u cronflow -f"
	@echo "    make logs            最近 200 行日志"

# ============ 本地开发 ============

install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install -e .
	cd frontend && npm install

dev: dev-backend

dev-backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8123

dev-frontend:
	cd frontend && npm run dev

migrate:
	cd backend && .venv/bin/alembic upgrade head

# ============ 构建 ============

build: build-frontend

build-frontend:
	cd frontend && npm run build

# ============ 部署 ============

ship:
	@if [ -z "$(SERVER)" ]; then \
		echo "ERROR: Please specify SERVER, e.g., make ship SERVER=user@your-server-ip"; \
		exit 1; \
	fi
	@echo "==> 1. Building frontend locally..."
	cd frontend && npm run build
	@echo "==> 2. Syncing code and build artifacts (excluding frontend sources)..."
	rsync -avz --delete --exclude-from=deploy/rsync-exclude.list ./ $(SERVER):/tmp/cronflow-src/
	@echo "==> 3. Running remote installation..."
	ssh -t $(SERVER) "cd /tmp/cronflow-src && sudo bash deploy/install.sh"

deploy:
	@if [ "$$(id -u)" -ne 0 ]; then \
		echo "需要 sudo 权限, 自动重试:"; \
		sudo bash deploy/install.sh; \
	else \
		bash deploy/install.sh; \
	fi

# ============ systemd 服务管理 (需 sudo) ============

status:
	sudo systemctl status cronflow

restart:
	sudo systemctl restart cronflow

stop:
	sudo systemctl stop cronflow

tail:
	sudo journalctl -u cronflow -f

logs:
	sudo journalctl -u cronflow -n 200 --no-pager

# ============ 清理 ============

clean:
	rm -rf backend/.venv backend/__pycache__ backend/app/**/__pycache__
	rm -rf frontend/dist frontend/node_modules frontend/.tsbuild-node
