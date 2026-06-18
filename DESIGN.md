# CronFlow 从零重实现 · 架构设计文档

> 本文档是在深入理解现有 CronFlow 项目核心需求后，制定的从零重实现架构方案。
> 现状参考：Flask + APScheduler(单进程) + Celery + PostgreSQL + Redis + Vue3/ElementPlus。

---

## 一、项目核心需求

CronFlow 是一个**分布式任务调度中心**：所有"可调度的事"都是 **Task**（任务），按 **kind** 区分处理器：

| Kind | 来源 | 处理器 |
|---|---|---|
| `python` | 开发期 `@register_task` 装饰函数（只读，不入库） | 调用注册函数 |
| `curl` | 运行期表单创建（入库 `tasks` 表） | httpx 抓取 → JSONB 缓存 |
| 未来 | shell / sql / webhook / ... | 扩展 handler 即可，不改调度层 |

调度层 **统一**：一个 `schedules` 表，每条调度引用一个 task（不论 kind），用 redbeat 在 Redis 上无状态分发。执行层一个统一 `worker.run_task`，按 kind 分派到对应 handler。

四件事的统一表达：
| 能力 | 实现 |
|---|---|
| **函数即任务** | `@register_task` + 参数自省 → 注册表（python kind） |
| **API 数据同步** | 表单建 curl task → handler_config 存 url/method/headers/... |
| **定时调度** | `schedules` 表 + redbeat → `worker.run_task(task_ref, ...)` 按 kind 分派 |
| **实时监控** | EventBus 单一出口，worker 完成时 emit `new_log`/`stats_update` |

数据模型四张表：`tasks`（curl 任务定义；python 不入库）、`schedules`（调度，引用 task_ref 字符串）、`task_logs`（执行日志）、`crawled_data_cache`（curl handler 的 JSONB 缓存输出）。

---

## 二、现有架构痛点

1. **调度器是单点 + 轮询全量同步**：状态全在单进程内存，daemon 挂了调度即停；5 秒延迟 + 全表扫。
2. **stats 每次全表 count**：每 5 秒 7 次 `count()` + 取最近日志，无缓存，日志表一大即拖垮。
3. **Schema 妥协**：`trigger_args`/`task_args` 用 `Text` 存 JSON 字符串而非 `JSONB`；时间字段存字符串而非 `timestamptz`（靠 "force UTC+8" 打补丁，治标不治本）。
4. **实时推送分散**：SocketIO emitter 在多文件各定义一份，曾出现 fd 泄漏。
5. **执行层缺鲁棒性**：无重试/退避/超时/并发限制/优先级/任务依赖/幂等。
6. **单体 Flask**：18 路由挤在 app.py，无分层、无认证。
7. **日志无生命周期**：只增不删，无分区无 TTL。

---

## 三、技术选型

| 层 | 现状 | 重设计 | 理由 |
|---|---|---|---|
| API 框架 | Flask | **FastAPI** | 原生异步、Pydantic 校验、自动 OpenAPI、与参数自省注册理念契合 |
| 任务注册 | `inspect` 自省 | 保留 `inspect` + 支持 **Pydantic 模型参数** | Pydantic 字段元信息更丰富，前端表单更精细 |
| 调度器 | APScheduler 单进程内存态 | **DB 为唯一真相源 + Redis 分布式锁选主 + 多实例** | 消除单点，任一实例挂掉其他接管 |
| 动态 beat | 手写 daemon 轮询 | **celery-redbeat**（schedule 存 Redis，动态增删 + leader election） | 动态调度标准解法，省掉自写轮询 |
| 队列 | Celery | **保留 Celery**，加 重试/超时/优先级/限流/幂等 | 成熟生态，不引入新概念 |
| DB | PostgreSQL | PostgreSQL（schema 规范化：JSONB 替代 Text、timestamptz 替代字符串、加索引） | 类型安全 + 可查询 |
| 实时推送 | SocketIO 散落 | **单一 EventBus 服务** | 收敛抽象边界，根治 fd 泄漏 |
| 前端 | Vue3 + Element Plus 单 App.vue | Vue3 + **Pinia + Vue Router + TS** 组件化 | 状态/路由/类型分层 |
| 可观测 | `print` | **结构化日志 + Prometheus metrics** | 生产级可观测 |
| 认证 | 无 | **JWT + RBAC** | 后台系统必备 |

---

## 四、分层架构

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend  (Vue3 + Pinia + Router + Element Plus + TS)       │
│  Dashboard / Tasks(python+curl) / Schedules / Logs / Cache   │
└───────────────┬─────────────────────────────┬────────────────┘
        HTTP/REST (FastAPI)             SocketIO (EventBus)
┌───────────────▼─────────────────────────────▼────────────────┐
│                    API Gateway (FastAPI)                      │
│  routers/  ·  schemas/  ·  services/  ·  auth/  ·  deps/      │
└──────┬─────────────────────────────────────┬─────────────────┘
       │                                     │ (dispatch run_task)
       │ (写 task / schedule)                 ▼
       ▼                          ┌──────────────────────────────┐
┌─────────────────┐               │  Scheduler Layer (无状态)     │
│  PostgreSQL     │◄──────────────│  · redbeat 周期 tick          │
│  tasks (curl)   │               │  · Redis SET NX 选主          │
│  schedules      │               │  · 到点 → send_task run_task   │
│  task_logs      │               │  · 多实例水平扩展             │
│  data_cache     │               └──────────────┬───────────────┘
└─────────────────┘                              │
       ▲                                         ▼
       │ 写日志/缓存       ┌──────────────────────────────────────┐
       │                  │  Celery Worker: worker.run_task       │
       │                  │  解析 task_ref → kind → 分派 handler  │
       │                  │  ├─ python_handler (调注册表函数)      │
       │                  │  └─ curl_handler   (httpx → 缓存)     │
       │                  │  统一: 重试/超时/幂等 + emit 事件     │
       │                  └──────────────┬───────────────────────┘
       │                                 │
       └────────────── Redis ────────────┘
         (broker + result + redbeat + RedisManager 扇出 + 锁)
```

**核心设计**：
1. **统一任务抽象**：python 任务来自 `@register_task`（启动期注册表），curl 任务来自表单（入 `tasks` 表）。`schedules.task_ref` 是字符串 ref，能在两处查找。
2. **调度层无状态化**：redbeat schedule 存 Redis，多 beat 实例 leader election，DB 是 schedule 配置真相源。
3. **执行层一个入口**：`worker.run_task(task_ref, ...)` 按 kind 分派到 handler，handler 共享日志/重试/emit 框架。

---

## 五、后端目录结构

```
backend/
├── app/main.py                 # FastAPI 入口
├── core/                       # 横切关注点
│   ├── config.py / db.py / db_sync.py / redis.py
│   ├── eventbus.py / eventbus_sync.py  # 单一 emit (RedisManager 跨进程扇出)
│   ├── security.py             # 鉴权接口（首版放行）
│   └── logging.py / metrics.py
├── models/                     # ORM (JSONB / timestamptz)
│   ├── task.py                 # tasks 表 (kind=curl 入库; python 不入库)
│   ├── schedule.py             # schedules 表 (task_ref 字符串)
│   ├── task_log.py / cache.py
├── schemas/
├── routers/                    # tasks / schedules / logs / cache / stats / health / metrics
├── services/                   # task_service / schedule_service / stats
├── registry/                   # @register_task + 参数自省 (python kind 来源)
├── scheduler/beat.py           # redbeat entry 增删 helper
├── worker/
│   ├── celery_app.py
│   ├── task_runner.py          # 唯一执行入口 worker.run_task
│   └── handlers/
│       ├── python_handler.py   # 调注册表函数
│       └── curl_handler.py     # httpx → JSONB 缓存
└── tasks/                      # 用户业务 python 任务
```

---

## 六、关键细节

### ① 任务注册（保留 + 增强）
```python
@register_task(name="清理临时文件", description="按目录和保留天数清理")
def cleanup_temp(path: str, keep_days: int = 7) -> dict:
    """..."""
```
自省产出结构化参数 schema（含 `required`/`default`/`type`/`description`），前端直接渲染表单——产品灵魂保留。增强：支持 Pydantic `BaseModel` 参数，前端拿完整 JSON Schema。

### ② 执行层鲁棒性（现状全无）
```python
@celery_app.task(
    bind=True,
    autoretry_for=(NetworkError, TimeoutError),
    retry_backoff=True, retry_max=3,
    time_limit=600, soft_time_limit=540,
    acks_late=True, reject_on_worker_lost=True,
)
```
+ 任务级并发限流（`rate_limit`）+ 幂等 key（`schedule_id + 触发时间` 去重，防重复执行）。

### ③ stats 物化（治本）
不再每 5 秒全表 count。二选一：
- 轻量：Redis 维护计数器（成功/失败/运行中用 `INCR/DECR`）；
- 重量：PostgreSQL 物化视图 + 定时 refresh。
日志表按月分区 + 90 天 TTL 自动清理。

---

## 七、设计原则总结

保留两个产品亮点：**装饰器注册 + JSONB 缓存**。
核心架构改动：**调度层无状态化（DB + Redis 锁 + redbeat）**。
执行层补齐：**重试/超时/幂等**。
基础设施：**FastAPI + Pydantic + 结构化可观测**。
