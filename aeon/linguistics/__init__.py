"""
AEON Chain-of-Linguistics (шаг 2.4).

Публичный API:
    ChainOfLinguistics — оркестратор (run/validate_layers)
    ChainResult        — результат цепочки
    LayerResult, LayerContext, Finding — типы
    LexicalLayer / SyntacticLayer / SemanticLayer / PragmaticLayer
    PROMPTS            — промпты слоёв (aeon/linguistics/prompts.py)
"""

from .base import Finding, LayerContext, LayerResult, LinguisticLayer
from .lexical import LexicalLayer
from .orchestrator import ChainOfLinguistics, ChainResult, detect_contradictions
from .pragmatic import PragmaticLayer
from .prompts import PROMPTS
from .semantic import SemanticLayer
from .syntactic import SyntacticLayer

__all__ = [
    "ChainOfLinguistics",
    "ChainResult",
    "LayerResult",
    "LayerContext",
    "Finding",
    "LinguisticLayer",
    "LexicalLayer",
    "SyntacticLayer",
    "SemanticLayer",
    "PragmaticLayer",
    "detect_contradictions",
    "PROMPTS",
]
