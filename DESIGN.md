# CronFlow 从零重实现 · 架构设计文档

> 本文档是在深入理解现有 CronFlow 项目核心需求后，制定的从零重实现架构方案。
> 现状参考：Flask + APScheduler(单进程) + Celery + PostgreSQL + Redis + Vue3/ElementPlus。

---

## 一、项目核心需求

CronFlow 是一个**分布式任务调度 + API 数据同步中心**，解决四件事：

| 能力 | 本质 |
|---|---|
| **函数即任务** | 用 `@register_task` 装饰 Python 函数，自动做参数类型自省，前端据此动态渲染表单 |
| **定时 + 即时调度** | `interval` / `cron` 两种触发；调度器到点 → 丢给 Celery 队列 → worker 异步执行 |
| **cURL/API 数据同步** | 导入 cURL 注册成轮询任务，抓回 JSON 写入 PostgreSQL 的 `JSONB` 缓存表，前端可查询预览 |
| **实时监控看板** | 4 张监控卡片 + 日志流，通过 SocketIO + Redis message queue 实时推送 |

三个进程角色分工：
- `app` —— API 网关 + SocketIO 服务端
- `scheduler_daemon` —— 调度仲裁者，每 5 秒全量扫表与内存 APScheduler 同步，到点 send_task 给 Celery
- `tasks_worker` —— Celery worker，真正执行任务、写日志、回推 SocketIO

四张表：`job_schedules`（调度配置）、`task_logs`（执行日志）、`curl_tasks`（cURL 同步任务）、`crawled_data_cache`（JSONB 抓取缓存）。

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
│  Dashboard / Schedules / TaskRegistry / DataSync / Logs      │
└───────────────┬─────────────────────────────┬────────────────┘
        HTTP/REST (FastAPI)             SocketIO (EventBus)
┌───────────────▼─────────────────────────────▼────────────────┐
│                    API Gateway (FastAPI)                      │
│  routers/  ·  schemas/  ·  services/  ·  auth/  ·  deps/      │
└──────┬─────────────────────────────────────┬─────────────────┘
       │                                     │ (dispatch)
       │ (写调度配置)                          ▼
       ▼                          ┌──────────────────────────────┐
┌─────────────────┐               │  Scheduler Layer (无状态)     │
│  PostgreSQL     │◄──────────────│  · redbeat 周期 tick          │
│  (唯一真相源)    │               │  · Redis SET NX 选主          │
│  schedules      │               │  · 到点 → send_task 给 Celery │
│  task_logs      │               │  · 多实例水平扩展             │
│  curl_tasks     │               └──────────────┬───────────────┘
│  data_cache     │                              │
└─────────────────┘                              ▼
       ▲                              ┌──────────────────────────────┐
       │ 写日志/缓存                   │  Celery Workers (执行层)      │
       │                              │  · 重试/退避/超时/限流/幂等   │
       │                              │  · python task / curl task   │
       │                              │  · 完成后 → EventBus.emit    │
       │                              └──────────────┬───────────────┘
       │                                             │
       └──────────── Redis ──────────────────────────┘
         (broker + result + redbeat + pub/sub + 锁)
```

**核心改动：调度层无状态化。**
- `job_schedules` 加 `next_run_time timestamptz` 索引；
- 调度器 N 实例跑同一 tick，redbeat leader election 只让一个实例发 tick；
- 到期任务 `send_task` 给 Celery 后立即更新 `next_run_time`。无单点，实例随便挂。

---

## 五、后端目录结构

```
backend/
├── app/main.py                 # FastAPI 入口
├── core/                       # 横切关注点
│   ├── config.py               # pydantic-settings
│   ├── db.py                   # async SQLAlchemy session
│   ├── redis.py
│   ├── security.py             # JWT/RBAC
│   └── eventbus.py             # 唯一 SocketIO emit 封装
├── models/                     # ORM 模型（JSONB / timestamptz）
├── schemas/                    # Pydantic 入参/出参
├── routers/                    # tasks / schedules / logs / curl / stats / auth
├── services/                   # 业务逻辑
├── registry/                   # @register_task + 参数自省（亮点保留）
│   ├── decorator.py
│   ├── introspect.py
│   └── discover.py
├── scheduler/                  # 无状态调度层
│   ├── beat.py                 # redbeat 配置
│   └── dispatch.py
├── worker/                     # Celery tasks
│   ├── celery_app.py
│   ├── python_runner.py        # 执行注册函数 + 日志 + 重试
│   └── curl_runner.py          # 抓取 + JSONB 缓存
└── tasks/                      # 业务任务（用户写的）
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
