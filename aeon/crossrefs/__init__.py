"""aeon.crossrefs — детекция кросс-ссылок между текстами (шаг 3.4.2).

Pair-based engine: `CrossReferenceEngine.detect(text_a, lang_a, text_b, lang_b)`
→ список validated cross-ref записей (schema 1.2.0). Пакет НЕ импортирует
`aeon.gold` (anti-leak, AST-скан в tests/test_crossrefs_engine.py).
"""

from .engine import CrossReferenceEngine
from .prompts import (CONFIDENCE_LEVELS, CROSS_REF_KINDS, FEW_SHOTS,
                      FORMULA_LABELS, build_prompt, render_examples)

__all__ = [
    "CrossReferenceEngine",
    "CROSS_REF_KINDS",
    "CONFIDENCE_LEVELS",
    "FORMULA_LABELS",
    "FEW_SHOTS",
    "build_prompt",
    "render_examples",
]
