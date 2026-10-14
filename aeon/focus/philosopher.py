"""AEON Multi-focus — роль «Философ»."""

from .base import FocusAnalysis, FocusContext, FocusRole
from .prompts import PHILOSOPHER_PROMPT


class PhilosopherRole(FocusRole):
    name = "philosopher"
    angle = "philosophical"

    def analyze(self, context: FocusContext) -> FocusAnalysis:
        return self._analyze_json(context, PHILOSOPHER_PROMPT)
