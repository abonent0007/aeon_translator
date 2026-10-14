"""AEON Linguistics — семантический слой (пропозиции, неоднозначности)."""

from .base import LayerContext, LayerResult, LinguisticLayer
from .prompts import SEMANTIC_PROMPT


class SemanticLayer(LinguisticLayer):
    """Семантика: пропозиции и честно помеченные неоднозначности."""

    name = "semantic"

    def analyze(self, context: LayerContext) -> LayerResult:
        return self._analyze_json(context, SEMANTIC_PROMPT)
