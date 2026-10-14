"""
AEON Fragment Hypotheses — типы (шаг 2.3).

Гипотеза — ВСЕГДА кандидат, не «истина»: confidence, evidence и
результат верификации (Detective) прикладываются явно.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Hypothesis:
    """Предлагаемое восстановление утраченного текста."""

    text: str
    confidence: float
    evidence: str = ""
    markers_addressed: List[str] = field(default_factory=list)
    source_refs: List[str] = field(default_factory=list)  # external_ids (если есть)
    verified: Optional[bool] = None                       # False = contradicted → отброшена
    verification: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "confidence": round(float(self.confidence), 4),
            "evidence": self.evidence,
            "markers_addressed": list(self.markers_addressed),
            "source_refs": list(self.source_refs),
            "verified": self.verified,
            "verification": self.verification,
        }


@dataclass
class NoReconstruction:
    """
    Терминальный вердикт прогона: восстановление невозможно/не выполнено.

    reason — структурированный сигнал для внешних источников:
      cruces_without_external_evidence → нужны внешние свидетельства (Ф2.6);
      max_confidence_below_threshold   → контекст не ограничивает (правильный ответ);
      all_contradicted                 → гипотезы отвергнуты Детективом;
      no_markers / llm_unavailable / llm_parse_error / llm_returned_none.
    """

    reason: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"reason": self.reason, "details": self.details}


@dataclass
class ReconstructionResult:
    """Результат движка: гипотезы ИЛИ терминальное no_reconstruction."""

    status: str  # "ok" | "no_reconstruction_possible"
    hypotheses: List[Hypothesis] = field(default_factory=list)
    no_reconstruction: Optional[NoReconstruction] = None
    markers_count: int = 0
    fragment_density: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "hypotheses": [hypothesis.to_dict() for hypothesis in self.hypotheses],
            "no_reconstruction": (
                self.no_reconstruction.to_dict() if self.no_reconstruction else None
            ),
            "markers_count": self.markers_count,
            "fragment_density": self.fragment_density,
        }
