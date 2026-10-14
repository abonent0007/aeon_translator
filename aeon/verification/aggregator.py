"""
AEON Verification 2.0 — CVI-агрегатор (комбинированный вердикт).

Правила свёртки (кураторские):
  1. любой negative (contradicted/incoherent) → итог contradicted;
  2. нет positives (все neutral/abstained) ИЛИ overall_confidence <
     abstention_threshold → abstained («Я не знаю»);
  3. иначе → verified; overall_confidence = среднее по положительным
     (нейтральные НЕ штрафуют); needs_review при conf < review_threshold.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .base import Verdict
from .verdicts import (
    VERDICT_ABSTAINED,
    VERDICT_CONTRADICTED,
    VERDICT_VERIFIED,
    is_negative,
    is_positive,
)


@dataclass
class CombinedVerdict:
    """Комбинированный вердикт трёх верификаторов."""

    verdict: str
    overall_confidence: float
    abstained: bool
    needs_review: bool
    verdicts: Dict[str, Verdict] = field(default_factory=dict)
    reasoning_trace: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "overall_confidence": self.overall_confidence,
            "abstained": self.abstained,
            "needs_review": self.needs_review,
            "verdicts": {name: verdict.to_dict() for name, verdict in self.verdicts.items()},
            "reasoning_trace": list(self.reasoning_trace),
        }


class Aggregator:
    """Свёртка вердиктов агентов в CombinedVerdict (CVI)."""

    def __init__(self, cfg, review_threshold: float = 0.85):
        self.cfg = cfg
        self.review_threshold = review_threshold

    def combine(self, verdicts: Dict[str, Verdict]) -> CombinedVerdict:
        trace = [
            {
                "agent": name,
                "verdict": verdict.verdict,
                "confidence": round(float(verdict.confidence), 4),
                "reasoning": verdict.reasoning,
                "sources": list(verdict.sources),
            }
            for name, verdict in verdicts.items()
        ]

        negatives = [v for v in verdicts.values() if is_negative(v.verdict)]
        if negatives:
            return CombinedVerdict(
                verdict=VERDICT_CONTRADICTED,
                overall_confidence=round(max(float(v.confidence) for v in negatives), 4),
                abstained=False,
                needs_review=False,
                verdicts=dict(verdicts),
                reasoning_trace=trace,
            )

        positives = [v for v in verdicts.values() if is_positive(v.verdict)]
        if not positives:
            return CombinedVerdict(
                verdict=VERDICT_ABSTAINED,
                overall_confidence=0.0,
                abstained=True,
                needs_review=False,
                verdicts=dict(verdicts),
                reasoning_trace=trace,
            )

        overall = round(sum(float(v.confidence) for v in positives) / len(positives), 4)

        if overall < self.cfg.abstention_threshold:
            return CombinedVerdict(
                verdict=VERDICT_ABSTAINED,
                overall_confidence=overall,
                abstained=True,
                needs_review=False,
                verdicts=dict(verdicts),
                reasoning_trace=trace,
            )

        return CombinedVerdict(
            verdict=VERDICT_VERIFIED,
            overall_confidence=overall,
            abstained=False,
            needs_review=overall < self.review_threshold,
            verdicts=dict(verdicts),
            reasoning_trace=trace,
        )
