"""
AEON Verification 2.0 — CVI-агрегатор (комбинированный вердикт).

Правила свёртки (кураторские; уточнены fix 2.7.2):
  1. любой negative (contradicted/incoherent) → итог contradicted;
  2. нет positives (все neutral/abstained) → abstained («Я не знаю»);
  3. **«один верификатор не сертифицирует»:** при `len(positives) < 2`
     и наличии хотя бы одного нейтрала → abstained (reason
     `insufficient_positives`) — одиночный позитив, разбавленный нейтральными,
     не даёт verified даже в 2-агентном basic-режиме;
  4. CVI = среднее по положительным (нейтральные НЕ штрафуют);
     CVI < abstention_threshold → abstained; иначе verified,
     needs_review при CVI < review_threshold.

`needs_review` остаётся False при `insufficient_positives`: система уверена,
что данных мало — review-флаг зарезервирован за verified с оговорками.
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
    reason: str = ""
    verdicts: Dict[str, Verdict] = field(default_factory=dict)
    reasoning_trace: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "overall_confidence": self.overall_confidence,
            "abstained": self.abstained,
            "needs_review": self.needs_review,
            "reason": self.reason,
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
                reason="negative_dominates",
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
                reason="no_positives",
                verdicts=dict(verdicts),
                reasoning_trace=trace,
            )

        overall = round(sum(float(v.confidence) for v in positives) / len(positives), 4)

        neutrals = [v for v in verdicts.values() if not is_positive(v.verdict)]
        if len(positives) < 2 and len(neutrals) >= 1:
            return CombinedVerdict(
                verdict=VERDICT_ABSTAINED,
                overall_confidence=overall,
                abstained=True,
                needs_review=False,
                reason="insufficient_positives",
                verdicts=dict(verdicts),
                reasoning_trace=trace,
            )

        if overall < self.cfg.abstention_threshold:
            return CombinedVerdict(
                verdict=VERDICT_ABSTAINED,
                overall_confidence=overall,
                abstained=True,
                needs_review=False,
                reason="below_threshold",
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
