"""
AEON Fragment Hypothesis Engine (шаг 2.3).

Публичный API:
    FragmentHypothesisEngine — оркестратор (reconstruct)
    Hypothesis               — кандидат восстановления
    NoReconstruction         — терминальный вердикт + reason
    ReconstructionResult     — результат прогона
"""

from .engine import DEFAULT_RECONSTRUCT_PROMPT, FragmentHypothesisEngine
from .hypothesis import Hypothesis, NoReconstruction, ReconstructionResult
from .ranking import cap_hypotheses, drop_contradicted, rank_hypotheses

__all__ = [
    "FragmentHypothesisEngine",
    "Hypothesis",
    "NoReconstruction",
    "ReconstructionResult",
    "rank_hypotheses",
    "cap_hypotheses",
    "drop_contradicted",
    "DEFAULT_RECONSTRUCT_PROMPT",
]
