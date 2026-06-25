"""cURL handler — httpx.AsyncClient 异步抓取 → 写入 JSON 缓存表。

handler_config:
  url, method (GET|POST|...), headers (dict), params (dict|None),
  data (dict|str|None), handler_type (PURE_JSON|NESTED_DATA|RAW_RESPONSE),
  target_collection, timeout?

params 语义:
  - 仅 dict, 表示要拼到 URL query 上的键值
  - URL 自带的 query 与 params 合并 (params 同名键覆盖 URL 自带)
  - 任意 method 都生效, GET 任务把参数放这里比塞进 data 更直观

data 序列化策略 (按 Content-Type 决定):
  - dict/list + Content-Type 含 'json'         → json=data (JSON body)
  - dict/list + Content-Type 含 'form-urlencoded' → data=data (form-encoded)
  - dict/list + 没指定 Content-Type            → json=data (默认 JSON)
  - str/bytes                                   → content=data (原样, 默认 form 头)

错误处理 (修复旧版问题):
- 4xx: 视为业务错误, raise RuntimeError (终态失败, 不重试)
- 5xx: raise httpx.HTTPStatusError (瞬态故障, 可重试)
- 网络错误 (TimeoutException/ConnectError): 瞬态故障, 可重试
"""
from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.cache import CrawledDataCache
from app.services.ref_resolver import ResolvedTask
from app.handlers.base import HandlerResult, TaskHandler

logger = get_logger("handler.curl")


def _get_content_type(headers: dict[str, str]) -> str:
    for k, v in headers.items():
        if k.lower() == "content-type":
            return v.lower()
    return ""


def _process_response(handler_type: str, status_code: int, body):
    if handler_type == "RAW_RESPONSE":
        return {"_raw": body if isinstance(body, str) else str(body), "_status": status_code}
    if isinstance(body, (dict, list)):
        if handler_type == "NESTED_DATA" and isinstance(body, dict):
            for key in ("data", "result", "items", "list", "results"):
                if key in body and isinstance(body[key], (list, dict)):
                    return body[key]
        return body
    # 标量 (bool/int/str/None): 包一层保留类型, 不丢信息
    return {"_value": body, "_status": status_code}


class CurlHandler(TaskHandler):
    kind = "curl"

    async def execute(
        self,
        session: AsyncSession,
        resolved: ResolvedTask,
        task_args: dict[str, Any],
    ) -> HandlerResult:
        cfg = resolved.handler_config or {}
        url = cfg.get("url") or ""
        method = (cfg.get("method") or "GET").upper()
        headers = dict(cfg.get("headers") or {})  # copy: 下方可能改写 Content-Type
        params = cfg.get("params") or None
        data = cfg.get("data")
        handler_type = cfg.get("handler_type") or "PURE_JSON"
        target_collection = cfg.get("target_collection") or "default"
        # 超时可配 (修复旧版硬编码 30s 问题)
        timeout = float(cfg.get("timeout") or settings.task_default_timeout)

        if not url:
            raise RuntimeError(f"curl task {resolved.ref} 缺少 url")

        req_kwargs: dict = {"method": method, "url": url, "headers": headers, "timeout": timeout}
        # query string: 显式 params 字段直接传给 httpx;
        # URL 自带的 ?a=b 由 httpx 自动保留, params 同名键会追加而非覆盖,
        # 故此处不再合并, 避免重复 (httpx 行为: URL query + params 都拼上)。
        if isinstance(params, dict) and params:
            req_kwargs["params"] = params

        if data is not None and method != "GET":
            ct = _get_content_type(headers)
            if isinstance(data, (dict, list)):
                if "form-urlencoded" in ct:
                    # form: httpx 会自动 urlencode + 保持 Content-Type
                    req_kwargs["data"] = data
                elif "json" in ct or not ct:
                    # JSON: httpx 会自动 json.dumps + 设 Content-Type
                    if not ct:
                        headers["Content-Type"] = "application/json"
                    req_kwargs["json"] = data
                else:
                    # 罕见: 自定义 Content-Type 但传了对象, 兜底走 JSON 序列化
                    req_kwargs["json"] = data
            else:
                # 字符串/字节 body, 原样发送; 未声明 Content-Type 时默认 form
                req_kwargs["content"] = data if isinstance(data, (bytes, bytearray)) else str(data)
                if not ct:
                    headers["Content-Type"] = "application/x-www-form-urlencoded"

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(**req_kwargs)

        # 4xx 是业务错误 (URL 错/token 过期等), 终态失败不重试
        if 400 <= resp.status_code < 500:
            raise RuntimeError(
                f"curl 请求返回 4xx: {resp.status_code} {resp.reason_phrase} — {resp.text[:500]}"
            )
        # 5xx 抛 HTTPStatusError, 由 executor 判定为瞬态可重试
        resp.raise_for_status()

        try:
            body = resp.json()
        except Exception:
            body = resp.text

        document = _process_response(handler_type, resp.status_code, body)
        # upsert 语义: 缓存只保留最新一条, 先删同 collection 的旧记录再插入。
        # 同一事务内由 executor 统一 commit, 失败回滚不会留下空缓存。
        await session.execute(
            delete(CrawledDataCache).where(CrawledDataCache.target_collection == target_collection)
        )
        session.add(CrawledDataCache(target_collection=target_collection, document=document))

        return HandlerResult(
            result_text=f"cached to {target_collection} (http {resp.status_code})",
            extra={"target_collection": target_collection, "status": resp.status_code},
        )


curl_handler = CurlHandler()
