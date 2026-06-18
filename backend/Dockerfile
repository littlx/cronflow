FROM python:3.12-slim

WORKDIR /app

# 系统依赖 (psycopg2 编译需要)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir .

COPY . .

EXPOSE 8000

# 默认启动 API; worker/beat 通过 docker-compose command 覆盖
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
