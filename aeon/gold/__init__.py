"""
AEON gold-standard harness (шаг 3.3).

Публичный API:
    load_dataset / GoldDataset / GoldRecord / GoldError — JSONL + integrity
    evaluate_dataset — метрики (P/R/F1 markers per kind, entities, is_fragment,
        completeness MAE, verdicts) — stdlib, без pandas/HF
    run_dataset / GoldPrediction — прогон pipeline (mock/real)
    build_report — markdown-отчёт
"""

from .loader import GoldDataset, GoldError, GoldRecord, load_dataset
from .metrics import evaluate_dataset
from .runner import GoldPrediction, run_dataset

__all__ = [
    "load_dataset",
    "GoldDataset",
    "GoldRecord",
    "GoldError",
    "evaluate_dataset",
    "run_dataset",
    "GoldPrediction",
    "build_report",
]


def build_report(*args, **kwargs):
    """Ленивая обёртка (report.py тянет больше зависимостей)."""
    from .report import build_report as _build

    return _build(*args, **kwargs)
