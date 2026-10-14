"""AEON Linguistics — лексический слой (леммы, части речи, морфология)."""

from .base import LayerContext, LayerResult, LinguisticLayer
from .prompts import LEXICAL_PROMPT


class LexicalLayer(LinguisticLayer):
    """Лексика: леммы, POS-теги, морфологические признаки. Standalone-слой."""

    name = "lexical"

    def analyze(self, context: LayerContext) -> LayerResult:
        return self._analyze_json(context, LEXICAL_PROMPT)
