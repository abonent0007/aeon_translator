"""
AEON LLM слой.

Публичный API:
    DeepSeekClient           — фасад (обратная совместимость v3.0)
    OpenAICompatibleProvider — провайдер (DeepSeek/OpenAI/локальные серверы)
    LLMProvider              — протокол провайдера
    LLMError                 — единая ошибка LLM-слоя
    extract_json             — извлечение/починка JSON из ответов LLM
    retry_call, is_retryable — ретраи с экспоненциальным backoff
"""

from .base import LLMError, LLMProvider
from .deepseek import DeepSeekClient
from .json_repair import extract_json
from .openai_compatible import OpenAICompatibleProvider
from .retries import is_retryable, retry_call

__all__ = [
    "DeepSeekClient",
    "LLMProvider",
    "LLMError",
    "OpenAICompatibleProvider",
    "extract_json",
    "retry_call",
    "is_retryable",
]
