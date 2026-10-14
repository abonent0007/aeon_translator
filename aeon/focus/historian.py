"""AEON Multi-focus — роль «Историк»."""

from .base import FocusAnalysis, FocusContext, FocusRole
from .prompts import HISTORIAN_PROMPT


class HistorianRole(FocusRole):
    name = "historian"
    angle = "historical_context"

    def analyze(self, context: FocusContext) -> FocusAnalysis:
        return self._analyze_json(context, HISTORIAN_PROMPT)
