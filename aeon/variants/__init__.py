"""
AEON Variant Readings (шаг 3.5) — выбор между attested readings.

Публичный API:
    load_apparatus / Apparatus / Locus / Reading / ApparatusError
    VariantEngine / VariantSelection / Selection
    SELECT_READING_PROMPT
"""

from .apparatus import (
    Apparatus,
    ApparatusError,
    Locus,
    Reading,
    load_apparatus,
    work_tokens,
)
from .engine import VariantEngine, VariantSelection
from .prompts import SELECT_READING_PROMPT
from .selector import ReadingSelector, Selection

__all__ = [
    "load_apparatus",
    "Apparatus",
    "Locus",
    "Reading",
    "ApparatusError",
    "work_tokens",
    "VariantEngine",
    "VariantSelection",
    "ReadingSelector",
    "Selection",
    "SELECT_READING_PROMPT",
]
