"""参数自省 — 从函数签名提取结构化参数 schema, 供前端动态渲染表单。

支持:
- 基础类型 str/int/float/bool/list/dict
- 默认值与 required 标记
- docstring 中的参数说明 (Google 风格 :param x: 说明)
- Pydantic BaseModel 参数 (生成完整 JSON Schema, 前端可精细渲染)
"""
from __future__ import annotations

import inspect
import re
from typing import Any

from pydantic import BaseModel, TypeAdapter

# 类型注解 -> 前端表单类型
_TYPE_MAP = {
    int: "int",
    float: "float",
    bool: "bool",
    str: "str",
    list: "list",
    dict: "dict",
}

_PARAM_DOC_RE = re.compile(r":param\s+\w+\s+(\w+):\s*(.+)")


def _extract_param_docs(docstring: str | None) -> dict[str, str]:
    """从 Google/Sphinx 风格 docstring 提取 :param name: 说明。"""
    if not docstring:
        return {}
    docs: dict[str, str] = {}
    for line in docstring.splitlines():
        m = _PARAM_DOC_RE.match(line.strip())
        if m:
            docs[m.group(1)] = m.group(2).strip()
    return docs


def _is_pydantic_model(annotation) -> bool:
    """判断注解是否为 Pydantic BaseModel 子类。"""
    try:
        return isinstance(annotation, type) and issubclass(annotation, BaseModel)
    except TypeError:
        return False


def introspect_parameters(func) -> list[dict[str, Any]]:
    """自省函数参数, 产出前端可消费的参数 schema 列表。"""
    sig = inspect.signature(func)
    param_docs = _extract_param_docs(func.__doc__)
    params: list[dict[str, Any]] = []

    for name, param in sig.parameters.items():
        annotation = param.annotation
        has_default = param.default is not inspect.Parameter.empty

        # Pydantic BaseModel: 生成完整 JSON Schema, 前端可精细渲染
        if _is_pydantic_model(annotation):
            schema = TypeAdapter(annotation).json_schema()
            params.append({
                "name": name,
                "type": "object",
                "schema": schema,
                "model_name": annotation.__name__,
                "default": None,
                "required": not has_default,
                "description": param_docs.get(name, "") or f"Pydantic 模型: {annotation.__name__}",
            })
            continue

        if annotation is inspect.Parameter.empty:
            ptype = "str"
        elif annotation in _TYPE_MAP:
            ptype = _TYPE_MAP[annotation]
        else:
            # 复杂类型记录类型名
            ptype = getattr(annotation, "__name__", str(annotation))

        params.append({
            "name": name,
            "type": ptype,
            "default": param.default if has_default else None,
            "required": not has_default,
            "description": param_docs.get(name, ""),
        })
    return params


def coerce_arg(value: Any, annotation) -> Any:
    """按函数注解把前端传来的值做类型转换。"""
    if annotation is inspect.Parameter.empty or value is None:
        return value
    # Pydantic 模型: 用 model_validate 转换
    if _is_pydantic_model(annotation):
        try:
            return annotation.model_validate(value)
        except Exception:
            return value
    try:
        if annotation is int:
            return int(value)
        if annotation is float:
            return float(value)
        if annotation is bool:
            return str(value).lower() in ("true", "1", "yes", "on")
    except (TypeError, ValueError):
        return value
    return value
