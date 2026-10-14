"""
AEON 结构化日志 — JSON Lines (одна JSON-строка на событие).
Только стандартная библиотека, без внешних зависимостей.

Каждое событие верификации/анализа содержит поля:
    ts, level, logger, msg + произвольные структурные поля
    (agent, verdict, confidence, sources, reasoning, ...).

Пример строки:
    {"ts": "2026-10-14T07:30:12.345Z", "level": "INFO", "logger": "aeon.verification",
     "msg": "verdict", "agent": "detective", "verdict": "grounded",
     "confidence": 0.87, "sources": ["Q859"], "reasoning": "exact quote found"}
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .config import CONFIG

DEFAULT_LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "aeon.jsonl"


def _default_log_path() -> Path:
    """Путь лог-файла по умолчанию: AEON_LOG_FILE (относительный — от корня проекта)."""
    path = Path(CONFIG.logging.log_file)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    return path


def _config_level() -> int:
    """Уровень логирования из конфига (AEON_LOG_LEVEL)."""
    return getattr(logging, str(CONFIG.logging.level).upper(), logging.INFO)

# Стандартные атрибуты LogRecord — не попадают в extras.
_RESERVED = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName", "message", "asctime",
}


class JsonLinesFormatter(logging.Formatter):
    """Форматтер: каждое событие — одна JSON-строка (JSON Lines)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
                  + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def get_logger(
    name: str = "aeon",
    log_file: Optional[Union[str, Path]] = None,
    level: Optional[int] = None,
) -> logging.Logger:
    """Логгер с JSON-lines handler'ом (файл: CONFIG.logging.log_file)."""
    logger = logging.getLogger(name)
    if getattr(logger, "_aeon_json_configured", False):
        return logger

    logger.setLevel(level if level is not None else _config_level())
    logger.propagate = False

    path = Path(log_file) if log_file is not None else _default_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(JsonLinesFormatter())
    logger.addHandler(handler)
    logger._aeon_json_configured = True  # type: ignore[attr-defined]
    return logger


def log_event(
    logger: logging.Logger,
    msg: str,
    *,
    agent: Optional[str] = None,
    verdict: Optional[str] = None,
    confidence: Optional[float] = None,
    sources: Optional[list] = None,
    reasoning: Optional[str] = None,
    trace_id: Optional[str] = None,
    **fields: Any,
) -> None:
    """Структурное событие (верификация/анализ): именованные поля + extras.

    trace_id связывает события одного прогона (например, трёх верификаторов
    одного атома на шаге 1.3). Параметр опционален — обратная совместимость.
    """
    extra: Dict[str, Any] = dict(fields)
    if agent is not None:
        extra["agent"] = agent
    if verdict is not None:
        extra["verdict"] = verdict
    if confidence is not None:
        extra["confidence"] = confidence
    if sources is not None:
        extra["sources"] = sources
    if reasoning is not None:
        extra["reasoning"] = reasoning
    if trace_id is not None:
        extra["trace_id"] = trace_id
    logger.info(msg, extra=extra)
