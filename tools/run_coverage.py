"""
Запуск coverage в обход pytest-cov.

Причина: на Windows связка pytest-cov-плагина (любой трейсер) с загрузкой
PyTorch DLL в наших тестах даёт access violation (0xC0000005).
Здесь Coverage стартует ДО pytest.main — обходной порядок, который
работает в изоляции (см. AGENTS.md → Known quirks).

Использование:
    python tools/run_coverage.py            # все тесты
    python tools/run_coverage.py tests/test_verification_agents.py
"""

import sys

import coverage

SOURCE = [
    "aeon.entity_linking",
    "aeon.crosswalk",
    "aeon.verification",
    "aeon.llm",
    "aeon.config",
    "aeon.metrics",
    "aeon.logging_config",
    "aeon.testing",
    "aeon.language",
    "aeon.fragments",
]


def main() -> int:
    args = sys.argv[1:] or ["tests"]

    cov = coverage.Coverage(source=SOURCE, timid=True)
    cov.start()
    code = 1
    try:
        import pytest

        code = pytest.main(["-q", *args])
    finally:
        cov.stop()
        cov.save()
    cov.report(show_missing=True)
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
