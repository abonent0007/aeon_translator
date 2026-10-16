"""
AEON LLM слой — ретраи с экспоненциальным backoff.

Ретраим только retryable-ошибки: HTTP 5xx, 408, 429, timeout/connection.
Прочие 4xx (400/401/403/404) — fail fast, без повторов.
"""

import time
from typing import Any, Callable, List, Optional, Tuple

RETRYABLE_STATUS = {408, 429}


def is_retryable(exc: BaseException) -> bool:
    """Классификация исключения: стоит ли повторить вызов."""
    try:
        import openai
    except ImportError:
        openai = None

    if openai is not None and isinstance(
            exc, (openai.APITimeoutError, openai.APIConnectionError)):
        return True

    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(exc, "status", None)
    if isinstance(status, int):
        return status in RETRYABLE_STATUS or status >= 500
    return False


def retry_after_seconds(exc: BaseException) -> Optional[float]:
    """Retry-After из ответа сервера (заголовок), в секундах. None если нет."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    value = headers.get("retry-after") or headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def retry_call(
    fn: Callable[[], Any],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    retryable: Callable[[BaseException], bool] = is_retryable,
    sleep: Callable[[float], None] = time.sleep,
    on_retry: Optional[Callable[[int, float, BaseException], None]] = None,
) -> Tuple[Any, int, List[float]]:
    """
    Вызывает fn с ретраями и экспоненциальным backoff.

    Returns: (результат, количество попыток, список задержек).
    Raises: последнее исключение, если попытки исчерпаны или ошибка неретраибельна.
    """
    delays: List[float] = []
    attempts = 0

    while True:
        attempts += 1
        try:
            return fn(), attempts, delays
        except Exception as exc:
            if attempts >= max(1, max_attempts) or not retryable(exc):
                raise
            delay = base_delay * (2 ** (attempts - 1))
            hint = retry_after_seconds(exc)
            if hint is not None:
                delay = max(delay, hint)
            delays.append(delay)
            if on_retry is not None:
                on_retry(attempts, delay, exc)
            sleep(delay)
