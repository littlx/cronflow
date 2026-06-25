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

## 生产部署 (极简单进程)

本系统支持极简部署：**仅需在服务器上运行 1 个 systemd 服务**。数据库使用 SQLite 单文件，编译后的前端静态资源直接由后端的 FastAPI 托管（通过 `STATIC_DIR` 静态目录配置），无需额外安装 Nginx 或 Caddy 服务。

> **关于前端同步**：
> 服务端部署**只需要传输编译打包好的 `frontend/dist` 目录**。前端的开发依赖（`node_modules/`）、源代码（`src/`）以及构建配置文件（`vite.config.ts`、`tsconfig.json` 等）仅在本地编译打包时需要，服务端无需保留。

### 一键部署 / 升级

在开发机上，直接执行以下 Makefile 命令（需指定远程服务器的 SSH 地址 `SERVER`）：

```bash
# 一键自动打包、精简同步、远程安装/升级
make ship SERVER=user@your-server-ip
```

该命令将自动为您完成以下 3 个步骤：
1. **本地构建前端**：在本地自动执行 `npm run build`。因配置了输出路径重定向，构建后的前端静态资源会直接生成在 `backend/dist/` 目录下。
2. **代码同步 (精简)**：使用 `rsync` 将项目同步到服务器临时目录（如 `/tmp/cronflow-src`）。**该过程通过 `deploy/rsync-exclude.list` 过滤，自动排除了整个 `frontend/` 文件夹（即所有的源码和 node_modules），仅随后端代码包一同上传已打包完成的 `backend/dist/`。**
3. **远程安装**：通过 SSH 在服务器上自动执行 `sudo bash deploy/install.sh` 进行安装或热更新。

> [!NOTE]
> `install.sh` 脚本会自动创建 `cronflow` 系统服务用户、在 `/opt/cronflow` 下配置虚拟环境、将前端静态目录绑定至后端托管，并开机自启 systemd 服务（服务在 `:8123` 端口暴露 API 与前端页面）。
>
> **升级服务**：后续修改代码后，再次在本地执行 `make ship SERVER=...` 即可（数据存放在 `/var/lib/cronflow/` 中，升级不会影响已有数据库数据）。

### 常用服务管理

```bash
# 服务状态与重启
sudo systemctl status cronflow
sudo systemctl restart cronflow

# 查看运行日志
sudo journalctl -u cronflow -f      # 实时追踪日志
sudo journalctl -u cronflow -n 200  # 查看最近 200 行日志

# 也可直接在仓库根目录下使用 Makefile 快捷命令
make status / make restart / make tail / make logs
```

### 反向代理 (可选)

如需启用 HTTPS 或配置自定义域名，可在服务前方架设一层 Nginx 或 Caddy：

```nginx
server {
    listen 443 ssl;
    server_name cronflow.internal;

    location / {
        proxy_pass http://127.0.0.1:8123;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;       # 确保 WebSocket 协议正常升级
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
    }
}
```

## 项目结构

```
cronflow-v2/
├── Makefile                   # 开发 + 部署常用命令
├── README.md
├── deploy/
│   ├── install.sh             # 服务器一键部署脚本
│   ├── cronflow.service       # systemd unit
│   ├── cronflow.env.example   # 配置示例
│   └── rsync-exclude.list     # rsync 过滤规则列表 (排除前端源码等)
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
└── backend/                   # 后端源码 + .venv + 前端打包产物 (backend/dist/)

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
