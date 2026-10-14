"""AEON Multi-focus — роль «Лингвист» (язык как культурно-историческое свидетельство)."""

from .base import FocusAnalysis, FocusContext, FocusRole
from .prompts import LINGUIST_PROMPT


class LinguistRole(FocusRole):
    name = "linguist"
    angle = "language_history"

    def analyze(self, context: FocusContext) -> FocusAnalysis:
        return self._analyze_json(context, LINGUIST_PROMPT)
