"""AEON Multi-focus — роль «Эзотерик» (opt-in; строгие guardrails, см. prompts.py)."""

from .base import FocusAnalysis, FocusContext, FocusRole
from .prompts import ESOTERIC_PROMPT


class EsotericRole(FocusRole):
    name = "esoteric"
    angle = "esoteric_symbolism"

    def analyze(self, context: FocusContext) -> FocusAnalysis:
        return self._analyze_json(context, ESOTERIC_PROMPT)
