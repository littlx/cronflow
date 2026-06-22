# CronFlow

> 单进程任务调度 + API 数据同步中心 (FastAPI + asyncio + SQLite + Vue3)

> 服务于 3 人内网, 极简部署: **2 容器** (backend + frontend nginx), **1 个 SQLite 文件** 即数据库。

## 特性

- **统一任务抽象**: python 任务 (`@register_task` 装饰函数, 参数自省) + curl 任务 (表单创建, JSON 缓存)
- **单进程调度**: asyncio 循环 + croniter, DB 为真相源, 无 Celery / Redis / 外部 broker
- **执行鲁棒**: 协程池 + 幂等表 + 指数退避重试 + 4xx 终态不重试 + 超时可配 + 崩溃 reconciliation
- **实时推送**: socketio 进程内 manager, 自动重连, 组件卸载时自动清理监听
- **可观测**: structlog 结构化日志 + Prometheus `/metrics` (TASK_TOTAL / TASK_DURATION / ACTIVE_SCHEDULES / REGISTERED_TASKS)
- **可插拔通知**: Notifier 协议 + Webhook 实现, 新增短信/邮件/钉钉/企微只加一个文件
- **认证预留**: 路由统一 `Depends(get_current_user)`, 首版放行, 接 JWT 时仅改 security.py

## 架构

```
                ┌───────────────────────────────────────┐
                │  Frontend (Vue3 + Element Plus + TS)   │
                │  Dashboard / Tasks / Schedules /      │
                │  Logs / Cache / Notifications / Metrics│
                └──────────────────┬────────────────────┘
                          HTTP/REST + SocketIO
                ┌──────────────────▼────────────────────┐
                │  FastAPI 单进程                         │
                │  ┌──────────┬──────────┬────────────┐  │
                │  │Scheduler │ Executor │ API Routers│  │
                │  │(asyncio) │(协程池)  │ (CRUD/分页)│  │
                │  │+croniter │+幂等表   │            │  │
                │  └────┬─────┴────┬─────┴─────┬──────┘  │
                │       └──────────┼───────────┘         │
                │                  ▼                     │
                │           ┌────────────┐               │
                │           │ SQLite WAL │               │
                │           │ cronflow.db│               │
                │           └────────────┘               │
                │                                        │
                │  Notifiers (webhook / sms / email ...) │
                └────────────────────────────────────────┘
```

## 启动

### Docker Compose (推荐)

```bash
make up            # 构建并启动 backend + frontend (2 容器)
make logs          # 查看实时日志
```

- 前端: http://localhost:5173
- 后端 API: http://localhost:8123  (`make ps` 可见)
- `/api/*` 与 `/socket.io/*` 由 nginx 反向代理到 backend
- SQLite 文件挂载在 docker volume `cronflow-data` 内, 备份只需拷贝该 volume

### 本地开发

需 Python >=3.11 + Node >=20:

```bash
# 后端
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
alembic upgrade head
uvicorn app.main:app --reload --port 8123

# 前端
cd frontend
npm install
npm run dev    # http://localhost:5173, proxy /api 与 /socket.io 到 8123
```

## 端到端验证

```bash
curl localhost:8123/health
curl localhost:8123/api/tasks                       # 列出 python 注册任务
curl -X POST localhost:8123/api/tasks/trigger \
  -H 'Content-Type: application/json' \
  -d '{"task_ref":"tasks.data_tasks.sleep_task","task_args":{"seconds":1}}'

# 前端 http://localhost:5173
# → 任务 → 立即执行
# → 定时调度 → 新建 interval 5 分钟
# → 通知 → 新建 webhook 配置, 勾选 task_failed → 收到失败任务的回调
# → 监控中心 / 指标 → 看实时计数与 Prometheus 指标
```

## 项目结构

```
cronflow-v2/
├── docker-compose.yml         # 2 容器编排
├── Makefile
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── alembic/               # 迁移 (initial schema 含 7 张表)
│   ├── app/
│   │   ├── main.py            # ASGI 入口: sio + FastAPI + lifespan
│   │   ├── core/              # config / db (aiosqlite+WAL) /
│   │   │                       eventbus / logging / metrics / security
│   │   ├── models/            # 7 张表 ORM
│   │   ├── schemas/           # Pydantic DTO
│   │   ├── routers/           # tasks/schedules/logs/cache/stats/
│   │   │                       notifications/metrics/health
│   │   ├── services/          # executor / scheduler / stats /
│   │   │                       schedule_service / task_service /
│   │   │                       notification_service / ref_resolver
│   │   ├── registry/          # @register_task + introspect (Pydantic
│   │   │                       BaseModel 支持) + discover
│   │   ├── handlers/          # base + python_handler + curl_handler
│   │   └── notifiers/         # base + webhook_notifier
│   └── tasks/                 # 用户业务 python 任务
└── frontend/
    ├── Dockerfile             # 两段式: node 构建 → nginx 提供
    ├── nginx.conf             # 静态资源 + 反代 /api + /socket.io + /metrics
    └── src/
        ├── api/               # client + types + 各 endpoint 模块
        ├── stores/            # Pinia (stats/tasks/schedules)
        ├── composables/       # useSocket / usePagination / useTable
        ├── components/        # 6 个公共组件
        └── views/             # 7 个 View
```

## 数据库表

| 表 | 用途 |
|---|---|
| `tasks` | curl 等表单创建任务定义 (python 任务不入库, 仅内存注册表) |
| `job_schedules` | 调度配置 + `next_run_time` (调度真相源) |
| `task_logs` | 执行日志, 重试时新建一行 (含 `attempt` 列) |
| `crawled_data_cache` | curl handler 写入的 JSON 文档 |
| `idempotency_keys` | 幂等去重表 (INSERT ON CONFLICT, 跨方言) |
| `notification_configs` | 通知渠道配置 (channel + config + events) |
| `notification_logs` | 通知发送记录 |

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

支持 `async def`, executor 自动识别。同步函数会用 `asyncio.to_thread` 包装防止阻塞 event loop。

## 新增通知渠道

实现 `Notifier` 协议 + 在 `app/notifiers/__init__.py` 注册:

```python
# app/notifiers/sms_notifier.py
class SmsNotifier:
    name = "sms"
    async def notify(self, event, config, context):
        # config 来自 notification_configs.config 列
        await send_sms(config["api_key"], config["template"], context["log"])

# app/notifiers/__init__.py
from app.notifiers.sms_notifier import SmsNotifier
NOTIFIERS["sms"] = SmsNotifier()
```

前端 NotificationsView 自动支持 (新 channel 仅需在 `<el-option>` 加一项)。

## 默认系统调度

启动时若不存在则自动创建:
- `[系统] 每日清理过期日志` — 每日 03:00, 保留 90 天
- `[系统] 每日清理过期缓存` — 每日 03:30, 保留 30 天

用户可在「定时调度」页禁用或修改, 删除后不会被自动复活。

## 配置项 (环境变量)

| 变量 | 默认 | 说明 |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./cronflow.db` | SQLite 文件位置 |
| `MAX_CONCURRENCY` | 8 | executor 协程池并发上限 |
| `TASK_RETRY_MAX` | 3 | 瞬态故障最大重试次数 |
| `TASK_RETRY_BACKOFF` | 2.0 | 退避基数, 实际等待 = base * 2^(attempt-1) |
| `TASK_DEFAULT_TIMEOUT` | 60 | handler 默认超时(秒) |
| `LOG_RETENTION_DAYS` | 90 | task_logs 保留天数 |
| `CACHE_RETENTION_DAYS` | 30 | crawled_data_cache 保留天数 |
| `SCHEDULER_TICK_SECONDS` | 5 | 调度循环扫描间隔 |
| `AUTH_ENABLED` | false | 首版预留, 接 JWT 后改 true |

## 范围边界

- JWT 登录 + RBAC (路由已 `Depends(get_current_user)`, 首版放行)
- task_logs 按月分区 (3 人量级用不上)
- 任务依赖 DAG
- 短信 / 邮件 / 钉钉 / 企微 通知 (骨架已就绪, 实现一行注册即可)
