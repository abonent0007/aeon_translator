"""
Общие фикстуры и утилиты тестов AEON v4.0.

MockLLM — детерминированная замена DeepSeekClient: без сети и ключей.
Ответы задаются по подстроке в последнем user-сообщении.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aeon.llm.json_repair import extract_json  # noqa: E402
from aeon.metrics import METRICS, reset_metrics  # noqa: E402


class MockLLM:
    """Детерминированный LLM-дублёр для тестов."""

    def __init__(
        self,
        responses: dict | None = None,
        default: str = "{}",
        available: bool = True,
    ):
        self.available = available
        self.responses = responses or {}
        self.default = default
        self.calls: list = []

    def _resolve(self, messages: list) -> str:
        text = messages[-1].get("content", "") if messages else ""
        for needle, value in self.responses.items():
            if needle in text:
                if isinstance(value, str):
                    return value
                return json.dumps(value, ensure_ascii=False)
        return self.default

    def _call(
        self, messages: list, temperature: float = 0.7, max_tokens: int = 2000
    ) -> str:
        self.calls.append(
            {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        )
        if not self.available:
            return ""
        return self._resolve(messages)

    def _call_json(
        self, messages: list, temperature: float = 0.3, max_tokens: int = 2000
    ) -> dict:
        raw = self._call(messages, temperature, max_tokens)
        if not raw:
            return {}
        data, reason = extract_json(raw)
        if reason is None:
            return data
        return {"raw_response": raw, "parse_error": reason}


@pytest.fixture
def mock_llm() -> MockLLM:
    """Пустой MockLLM; ответы задаются в тесте: mock_llm.responses = {...}."""
    return MockLLM()


@pytest.fixture
def sample_structure() -> dict:
    """Типовая структура, которую LLM-экстрактор возвращает для простого текста."""
    return {
        "intent": "statement",
        "domain": "philosophy",
        "entities": [
            {
                "name": "Александр Македонский",
                "type": "person",
                "role": "agent",
                "span": "Александр Македонский",
                "confidence": 0.9,
            },
        ],
        "semantic_roles": {"agent": "Александр Македонский"},
        "evidence": ["example quote"],
        "explanation_chain": ["step 1", "step 2"],
        "confidence_breakdown": {
            "intent": 0.9,
            "domain": 0.8,
            "entities": 0.9,
            "roles": 0.7,
        },
        "complexity": 0.5,
        "urgency": 0.2,
        "extraction_confidence": 0.85,
        "semantic_tokens": ["империя", "завоевание"],
    }


@pytest.fixture(autouse=True)
def _clean_metrics():
    """Метрики не протекают между тестами."""
    reset_metrics()
    yield
    reset_metrics()


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Сводка метрик AEON в конце pytest-сессии."""
    terminalreporter.write_sep("=", "AEON metrics summary")
    terminalreporter.write_line(METRICS.format_summary())
