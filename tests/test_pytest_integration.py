"""Интеграционный тест: pytest_terminal_summary выводит метрики AEON."""

import subprocess
import sys


def test_pytest_terminal_summary_shows_metrics():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_smoke.py", "-q", "--no-header",
         "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )

    assert "AEON metrics summary" in result.stdout
    assert "atoms_processed" in result.stdout
    assert "cache_hit_rate" in result.stdout
