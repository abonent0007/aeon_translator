"""
AEON morphology (шаг 3.2) — morph_v1: LLM-морфология древних языков.

Публичный API:
    MorphEngine / morph_engine  — text + forms → разбор каждой формы
    MORPH_V1_PROMPT             — контракт-промпт (contract v1)
"""

from .engine import MorphEngine, morph_engine
from .prompts import MORPH_FIELDS, MORPH_V1_PROMPT

__all__ = ["MorphEngine", "morph_engine", "MORPH_V1_PROMPT", "MORPH_FIELDS"]
