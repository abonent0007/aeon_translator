"""
Обратная совместимость v3.0: модуль переехал в aeon/llm/.

Реэкспорт: `from aeon.llm_client import DeepSeekClient` продолжает работать.
Новый код должен импортировать из `aeon.llm`.
"""

from .llm import DeepSeekClient, LLMError  # noqa: F401

__all__ = ["DeepSeekClient", "LLMError"]
