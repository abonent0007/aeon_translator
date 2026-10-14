"""AEON Linguistics — прагматический слой (речевые акты, тональность, импликатуры)."""

from .base import LayerContext, LayerResult, LinguisticLayer
from .prompts import PRAGMATIC_PROMPT


class PragmaticLayer(LinguisticLayer):
    """Прагматика: намерение, контекст, что подразумевается без слов."""

    name = "pragmatic"

    def analyze(self, context: LayerContext) -> LayerResult:
        return self._analyze_json(context, PRAGMATIC_PROMPT)
