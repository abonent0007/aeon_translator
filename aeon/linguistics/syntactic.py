"""AEON Linguistics — синтаксический слой (зависимости, согласование)."""

from .base import LayerContext, LayerResult, LinguisticLayer
from .prompts import SYNTACTIC_PROMPT


class SyntacticLayer(LinguisticLayer):
    """Синтаксис: структура клауз, зависимость, согласование/управление."""

    name = "syntactic"

    def analyze(self, context: LayerContext) -> LayerResult:
        return self._analyze_json(context, SYNTACTIC_PROMPT)
