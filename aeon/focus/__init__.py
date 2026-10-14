"""
AEON Multi-focus Analysis (шаг 2.5).

Публичный API:
    MultiFocusOrchestrator — параллельный запуск ролей
    MultiFocusResult       — сводка (insights_by_role, all_disagree)
    FocusAnalysis, Insight, FocusContext, FocusRole — типы
    Роли: HistorianRole / PhilosopherRole / LinguistRole / EsotericRole
    PROMPTS — промпты ролей (aeon/focus/prompts.py)
"""

from .aggregator import MultiFocusResult, aggregate
from .base import FocusAnalysis, FocusContext, FocusRole, Insight
from .esoteric import EsotericRole
from .historian import HistorianRole
from .linguist import LinguistRole
from .orchestrator import ALL_ROLES, DEFAULT_ROLES, MultiFocusOrchestrator
from .philosopher import PhilosopherRole
from .prompts import PROMPTS

__all__ = [
    "MultiFocusOrchestrator",
    "MultiFocusResult",
    "FocusAnalysis",
    "FocusContext",
    "FocusRole",
    "Insight",
    "HistorianRole",
    "PhilosopherRole",
    "LinguistRole",
    "EsotericRole",
    "aggregate",
    "DEFAULT_ROLES",
    "ALL_ROLES",
    "PROMPTS",
]
