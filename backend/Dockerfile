FROM python:3.12-slim

WORKDIR /app

# 系统依赖 (SQLite + 编译头)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir .

COPY . .

# 默认 SQLite 文件路径在 /data, 容器外用 volume 挂载持久化
ENV DATABASE_URL=sqlite+aiosqlite:////data/cronflow.db
RUN mkdir -p /data

EXPOSE 8123

# 启动: 先跑迁移, 再起 uvicorn
CMD bash -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8123"
