"""
Общие фикстуры и утилиты тестов AEON v4.0.

MockLLM вынесен в aeon/testing.py (общий с demo).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aeon.metrics import METRICS, reset_metrics  # noqa: E402
from aeon.testing import MockLLM  # noqa: E402


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
