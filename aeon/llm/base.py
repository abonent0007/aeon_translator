"""
AEON LLM слой — базовые типы.

LLMProvider — протокол чат-провайдера; LLMError — единая ошибка слоя
(после исчерпания ретраев или при неретраибельной ошибке).
"""

from typing import Dict, List, Optional, Protocol, runtime_checkable


class LLMError(RuntimeError):
    """Ошибка LLM-вызова (ретраи исчерпаны или ошибка неретраибельна)."""

    def __init__(
        self,
        message: str,
        *,
        attempts: int = 1,
        last_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.attempts = attempts
        self.last_error = last_error


@runtime_checkable
class LLMProvider(Protocol):
    """Протокол LLM-провайдера (chat-интерфейс OpenAI-совместимого типа)."""

    name: str
    model: str

    @property
    def available(self) -> bool:  # pragma: no cover - protocol
        ...

    def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        trace_id: Optional[str] = None,
    ) -> str:  # pragma: no cover - protocol
        ...
