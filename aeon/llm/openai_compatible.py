"""
AEON LLM слой — OpenAI-совместимый провайдер.

Работает с DeepSeek, OpenAI и локальными серверами (vLLM / Ollama / LM Studio),
поддерживающими Chat Completions API. Внутри: ретраи с backoff и
JSON-lines логирование каждого вызова (provider/model/latency/retries/trace_id).
"""

import time
from typing import Any, Callable, Dict, List, Optional

from ..logging_config import get_logger, log_event
from .base import LLMError
from .retries import retry_call

try:
    from openai import OpenAI

    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False


class OpenAICompatibleProvider:
    """Чат через OpenAI Chat Completions API (совместимые endpoints)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "deepseek-chat",
        *,
        name: str = "openai-compatible",
        timeout: float = 60.0,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        trace_id: Optional[str] = None,
        client: Any = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.name = name
        self.model = model
        self.trace_id = trace_id
        self.timeout = timeout
        self.max_attempts = max(1, int(max_attempts))
        self.base_delay = base_delay
        self._sleep = sleep
        self._logger = get_logger("aeon.llm")
        # Cost-tracking (2.7.7): накопительные счётчики за жизнь провайдера.
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cache_hit_tokens = 0  # 2.7.3: prompt_cache_hit_tokens (DeepSeek)

        if client is not None:
            self._client = client
        elif api_key and _HAS_OPENAI:
            self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        else:
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    @property
    def client(self):
        return self._client

    def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        trace_id: Optional[str] = None,
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Вызов chat completion с ретраями. "" если провайдер недоступен."""
        if self._client is None:
            return ""

        tid = trace_id if trace_id is not None else self.trace_id
        t0 = time.perf_counter()
        retry_delays: List[float] = []

        def on_retry(attempt: int, delay: float, exc: BaseException) -> None:
            retry_delays.append(delay)
            log_event(
                self._logger,
                "llm_retry",
                provider=self.name,
                model=self.model,
                attempt=attempt,
                delay_sec=round(delay, 3),
                error=str(exc)[:200],
                trace_id=tid,
            )

        create_kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if extra_body:
            create_kwargs["extra_body"] = extra_body

        try:
            response, _attempts, _delays = retry_call(
                lambda: self._client.chat.completions.create(**create_kwargs),
                max_attempts=self.max_attempts,
                base_delay=self.base_delay,
                sleep=self._sleep,
                on_retry=on_retry,
            )
        except Exception as exc:
            latency_ms = round((time.perf_counter() - t0) * 1000, 1)
            log_event(
                self._logger,
                "llm_call",
                provider=self.name,
                model=self.model,
                latency_ms=latency_ms,
                attempts=len(retry_delays) + 1,
                retries=len(retry_delays),
                ok=False,
                error=str(exc)[:200],
                trace_id=tid,
            )
            raise LLMError(
                f"LLM call failed: {exc}",
                attempts=len(retry_delays) + 1,
                last_error=exc,
            ) from exc

        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        usage = getattr(response, "usage", None)
        tokens_in = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
        tokens_out = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0
        # Note 4 (куратор): поле может отсутствовать — graceful .get/getattr
        tokens_cache_hit = (int(getattr(usage, "prompt_cache_hit_tokens", 0) or 0)
                            if usage else 0)
        self.calls += 1
        self.prompt_tokens += tokens_in
        self.completion_tokens += tokens_out
        self.cache_hit_tokens += tokens_cache_hit
        log_event(
            self._logger,
            "llm_call",
            provider=self.name,
            model=self.model,
            latency_ms=latency_ms,
            attempts=len(retry_delays) + 1,
            retries=len(retry_delays),
            ok=True,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            tokens_cache_hit=tokens_cache_hit,
            trace_id=tid,
        )
        return response.choices[0].message.content
