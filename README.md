# CronFlow v2

> 分布式任务调度 + API 数据同步中心 (FastAPI + Celery + celery-redbeat + PostgreSQL + Redis + Vue3)

这是 CronFlow 的从零重实现版本。架构设计见 [DESIGN.md](./DESIGN.md)。

## 与 v1 的核心区别

| 维度 | v1 | v2 |
|---|---|---|
| API | Flask | FastAPI (async + Pydantic) |
| 调度 | APScheduler 单进程内存态 | **celery-redbeat 无状态化** (DB 真相源 + Redis 选主 + 多实例) |
| Schema | Text 存 JSON、字符串存时间 | JSONB / timestamptz, Alembic 迁移 |
| 执行 | 无重试/超时/幂等 | 重试+退避+超时+幂等 key |
| 实时推送 | SocketIO 散落 (曾 fd 泄漏) | 单一 EventBus 出口 |
| stats | 每 5s 全表 count | Redis 计数器 + 事件驱动推送 |
| 可观测 | print | structlog + Prometheus |
| 认证 | 无 | JWT/RBAC 接口预留 |

## 架构

```
Frontend ──HTTP──▶ FastAPI (routers/services) ──写DB──▶ PostgreSQL
            └──SocketIO──▶ EventBus (唯一出口)
                                    ▲
                          Redis message_queue
                                    ▲
Celery beat (redbeat) ──tick──▶ send_task ──▶ Celery worker
                                                   │
                                          执行 python/curl task
                                          写日志 + Redis 计数器
                                          emit new_log/stats_update
```

## 启动

### Docker Compose (推荐)

```bash
cd cronflow-v2
make up            # 构建 + 启动 pg/redis/backend/worker/beat/frontend
make migrate       # alembic upgrade head (建四张表)
```

- 前端: http://localhost:5174
- 后端 API: http://localhost:8000
- PostgreSQL: localhost:5433 (避免与 v1 的 5432 冲突)
- Redis: localhost:6380

### 本地开发

需本地 pg(5433) + redis(6380):

```bash
make dev          # uvicorn API
make dev-worker   # celery worker
make dev-beat     # celery beat (redbeat)
```

## 端到端验证

```bash
# 1. health
curl localhost:8000/health
# 2. 列注册任务
curl localhost:8000/api/tasks
# 3. 前端 http://localhost:5174 → 任务注册 → 立即执行 → 监控中心看日志实时刷新
# 4. 定时调度 → 建 interval 5 分钟 → 到点自动执行
# 5. 数据同步 → 导入 cURL → 启用轮询 → 预览缓存
```

## 项目结构

```
cronflow-v2/
├── docker-compose.yml
├── Makefile
├── DESIGN.md
├── backend/
│   ├── pyproject.toml
│   ├── alembic/                # 迁移
│   ├── app/                    # FastAPI 应用
│   │   ├── main.py
│   │   ├── core/               # config/db/redis/eventbus/security/logging/metrics
│   │   ├── models/             # ORM (JSONB/timestamptz)
│   │   ├── schemas/            # Pydantic
│   │   ├── routers/            # tasks/schedules/logs/curl/stats/health/metrics
│   │   ├── services/           # 业务逻辑
│   │   └── registry/           # @register_task + 参数自省 (亮点保留)
│   ├── scheduler/              # redbeat entry 增删 helper
│   ├── worker/                 # celery_app + python_runner + curl_runner
│   └── tasks/                  # 用户业务任务
└── frontend/
    └── src/                    # Vue3 + Pinia + Router + TS + Element Plus
        ├── api/ stores/ composables/ components/ views/
```

## 开发任务

在 `backend/tasks/` 下新建 `.py`, 用 `@register_task` 装饰函数即自动注册为可视化任务:

```python
from app.registry import register_task

@register_task(name="我的任务", description="...")
def my_task(path: str, count: int = 10) -> dict:
    """参数会被自动自省, 前端据此渲染表单。

    :param path: 处理路径
    :param count: 处理数量
    """
    return {"path": path, "count": count}
```

## 范围边界 (首版未做, 留 TODO)

- JWT 登录 + RBAC (路由已 Depends(get_current_user), 首版放行)
- task_logs 按月分区 (首版普通表 + cleanup_old_logs TTL 任务)
- 物化视图 stats (首版 Redis 计数器)
- 任务依赖 DAG
