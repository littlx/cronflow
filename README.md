# CronFlow

> 单进程任务调度 + API 数据同步中心 (FastAPI + asyncio + SQLite + Vue3)

> 服务于 3 人内网, 极简部署: **1 个 systemd 服务** + **1 个 SQLite 文件**, 前端打包后由 FastAPI 的 StaticFiles 托管, 单端口同域提供 API、WebSocket、SPA。

## 特性

- **统一任务抽象**: python 任务 (`@register_task` 装饰函数, 参数自省) + curl 任务 (表单创建, JSON 缓存)
- **单进程调度**: asyncio 循环 + croniter, DB 为真相源, 无 Celery / Redis / 外部 broker
- **执行鲁棒**: 协程池 + 幂等表 + 指数退避重试 + 4xx 终态不重试 + 超时可配 + 崩溃 reconciliation
- **实时推送**: socketio 进程内 manager, 自动重连, 组件卸载时自动清理监听
- **可观测**: structlog 结构化日志 + Prometheus `/metrics`
- **可插拔通知**: Notifier 协议 + Webhook 实现, 新增短信/邮件/钉钉/企微只加一个文件
- **同端口同域**: 前端 dist 由 FastAPI StaticFiles 托管, 无需 nginx, Vue Router HTML5 history 由 SPA fallback 兜底
- **认证预留**: 路由统一 `Depends(get_current_user)`, 首版放行, 接 JWT 时仅改 security.py

## 架构

```
                         浏览器
                            │
                       (单一域名)
                            │
                ┌───────────▼───────────────┐
                │  uvicorn (FastAPI)         │
                │  ┌──────────────────────┐  │
                │  │  /api/*       REST   │  │
                │  │  /socket.io/* WS     │  │
                │  │  /metrics     prom   │  │
                │  │  /assets/*    static │  │
                │  │  /{any}       SPA    │  │ ← Vue Router history 兜底
                │  └──────────────────────┘  │
                │                            │
                │  内部: scheduler loop +    │
                │       executor 协程池 +    │
                │       socketio 内存 mgr    │
                │                            │
                │       SQLite WAL           │
                │       cronflow.db          │
                └────────────────────────────┘
                            │
                       systemd
```

## 本地开发

需 Python >=3.11 + Node >=20。

```bash
# 一次性安装依赖
make install              # 后端 venv + 前端 npm

# 起后端 (uvicorn :8123)
make dev

# 另开终端起前端 dev server (vite :5173, proxy /api /socket.io 到 :8123)
make dev-frontend
```

访问 http://localhost:5173, vite 会代理后端请求。

> **开发期推荐用两端口**: vite dev server 提供 HMR, 后端不挂 SPA(STATIC_DIR 不设置)。

## 构建 + 部署 (生产)

> 部署目标: 一台 Linux 服务器, 走 systemd 管理。

### 1. 在仓库内构建前端

任意机器 (本地或 CI) 上:

```bash
make build      # 生成 frontend/dist
```

### 2. 把整个仓库同步到服务器

```bash
rsync -av --exclude='.venv' --exclude='node_modules' --exclude='*.db*' \
    ./ user@server:/tmp/cronflow-src/
```

### 3. 在服务器上执行安装脚本

```bash
ssh user@server
cd /tmp/cronflow-src
sudo bash deploy/install.sh
# 或 sudo make deploy
```

`install.sh` 会:

1. 创建 `cronflow` 系统用户与组
2. 同步后端源码到 `/opt/cronflow/backend`, 创建 venv 并 `pip install -e .`
3. 同步 `frontend/dist` 到 `/opt/cronflow/frontend`
4. 创建数据目录 `/var/lib/cronflow` (SQLite 文件位置)
5. 安装配置示例 `/etc/cronflow/cronflow.env`
6. 安装 `/etc/systemd/system/cronflow.service`
7. `systemctl enable --now cronflow`

启动后, 服务在 `:8123` 暴露 API + SPA。浏览器访问 `http://<server-ip>:8123/` 即可。

> 升级: 改完代码 → `make build` → 重新 rsync → `sudo bash deploy/install.sh` (会保留 `/var/lib/cronflow` 数据)。

### 4. 常用服务管理

```bash
sudo systemctl status cronflow      # 状态
sudo systemctl restart cronflow     # 重启
sudo journalctl -u cronflow -f      # 实时日志
sudo journalctl -u cronflow -n 200  # 最近 200 行

# 或用 Makefile (本仓库下)
make status / make restart / make tail / make logs
```

### 5. 反向代理 (可选)

如需 HTTPS、域名、统一接入点, 在前面架一层 nginx/caddy:

```nginx
server {
    listen 443 ssl;
    server_name cronflow.internal;

    location / {
        proxy_pass http://127.0.0.1:8123;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;       # WebSocket
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
    }
}
```

CronFlow 启动时带 `--proxy-headers --forwarded-allow-ips='*'`, 反代头会被正确识别。

## 项目结构

```
cronflow-v2/
├── Makefile                   # 开发 + 部署常用命令
├── README.md
├── deploy/
│   ├── install.sh             # 服务器一键部署脚本
│   ├── cronflow.service       # systemd unit
│   └── cronflow.env.example   # 配置示例
├── backend/
│   ├── pyproject.toml
│   ├── alembic/               # 迁移 (initial schema 含 7 张表)
│   └── app/
│       ├── main.py            # ASGI 入口: sio + FastAPI + StaticFiles + SPA fallback
│       ├── core/              # config / db (aiosqlite+WAL) / eventbus /
│       │                       logging / metrics / security
│       ├── models/            # 7 张表 ORM
│       ├── schemas/           # Pydantic DTO
│       ├── routers/           # tasks/schedules/logs/cache/stats/
│       │                       notifications/metrics/health
│       ├── services/          # executor / scheduler / stats /
│       │                       schedule_service / task_service /
│       │                       notification_service / ref_resolver
│       ├── registry/          # @register_task + introspect (Pydantic
│       │                       BaseModel JSON Schema 支持) + discover
│       ├── handlers/          # base + python_handler + curl_handler
│       └── notifiers/         # base + webhook_notifier
├── backend/tasks/             # 用户业务 python 任务
└── frontend/
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── api/               # client + types + 各 endpoint 模块
        ├── stores/            # Pinia (stats/tasks/schedules)
        ├── composables/       # useSocket / usePagination / useTable
        ├── components/        # 6 个公共组件
        └── views/             # 7 个 View
```

部署到服务器后:

```
/opt/cronflow/
├── backend/                   # 后端源码 + .venv
└── frontend/                  # 前端 dist (FastAPI 用 STATIC_DIR 指向)

/var/lib/cronflow/cronflow.db  # SQLite 数据库
/etc/cronflow/cronflow.env     # 运行配置 (覆盖 unit Environment=)
/etc/systemd/system/cronflow.service
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
        await send_sms(config["api_key"], config["template"], context["log"])

# app/notifiers/__init__.py
from app.notifiers.sms_notifier import SmsNotifier
NOTIFIERS["sms"] = SmsNotifier()
```

前端 NotificationsView 自动支持 (channel 下拉里加一项即可)。

## 默认系统调度

启动时若不存在则自动创建:

- `[系统] 每日清理过期日志` — 每日 03:00, 保留 90 天
- `[系统] 每日清理过期缓存` — 每日 03:30, 保留 30 天

用户可在「定时调度」页禁用或修改, 删除后不会被自动复活。

## 配置项 (环境变量)

可写在 `/etc/cronflow/cronflow.env`, systemd 会自动加载:

| 变量 | 默认 | 说明 |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:////var/lib/cronflow/cronflow.db` | SQLite 文件位置 |
| `STATIC_DIR` | `/opt/cronflow/frontend` | 前端 dist 目录, 留空则不托管 SPA |
| `MAX_CONCURRENCY` | 8 | executor 协程池并发上限 |
| `TASK_RETRY_MAX` | 3 | 瞬态故障最大重试次数 |
| `TASK_RETRY_BACKOFF` | 2.0 | 退避基数, 实际等待 = base * 2^(attempt-1) |
| `TASK_DEFAULT_TIMEOUT` | 300 | handler 默认超时(秒), 5 分钟 |
| `LOG_RETENTION_DAYS` | 90 | task_logs 保留天数 |
| `CACHE_RETENTION_DAYS` | 30 | crawled_data_cache 保留天数 |
| `SCHEDULER_TICK_SECONDS` | 5 | 调度循环扫描间隔 |
| `AUTH_ENABLED` | false | 首版预留, 接 JWT 后改 true |

## 备份

```bash
sudo systemctl stop cronflow
sudo cp /var/lib/cronflow/cronflow.db ~/backup-$(date +%F).db
sudo systemctl start cronflow
```

SQLite WAL 模式下也可热备 (用 `sqlite3 .backup`):

```bash
sudo -u cronflow sqlite3 /var/lib/cronflow/cronflow.db \
    ".backup /tmp/cronflow-$(date +%F).db"
```

## 范围边界 (按需扩展)

- JWT 登录 + RBAC (路由已 `Depends(get_current_user)`, 首版放行)
- task_logs 按月分区 (3 人量级用不上)
- 任务依赖 DAG
- 短信 / 邮件 / 钉钉 / 企微 通知 (骨架已就绪, 实现一行注册即可)
