"""结构化日志 (structlog) 配置。

全项目统一用 get_logger() 取 logger, 不再用 print。
单进程架构下日志出口唯一, 配置一次即可。
"""
from __future__ import annotations

import logging
import sys

import structlog


def setup_logging() -> None:
    """配置 structlog + 标准 logging。开发环境用彩色控制台输出。"""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "cronflow"):
    return structlog.get_logger(name)
