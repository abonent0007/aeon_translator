"""
AEON Variant Readings — оркестратор (шаг 3.5).

Порядок в pipeline фиксирован: reconstruct (шаг 1.6, восстановление lacunae
делает контекст полнее) → variant (шаг 1.9, выбор среди attested readings
на более полном контексте). Work mismatch (все значимые токены
apparatus.work обязаны присутствовать в work_hint) → ConfigError —
никаких тихих неправильных результатов.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..config import ConfigError
from ..llm_client import DeepSeekClient
from ..logging_config import get_logger, log_event
from .apparatus import Apparatus, work_tokens
from .selector import ReadingSelector, Selection


@dataclass
class VariantSelection:
    """Результат прогона: selections по loci + бюджет."""

    apparatus_version: str
    work: str
    selections: List[Selection] = field(default_factory=list)
    trace_id: Optional[str] = None
    llm_calls: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "apparatus_version": self.apparatus_version,
            "work": self.work,
            "selections": [selection.to_dict() for selection in self.selections],
            "trace_id": self.trace_id,
            "llm_calls": self.llm_calls,
        }


class VariantEngine:
    """Обход loci аппарата + work-guard + селектор."""

    def __init__(self, llm_client=None, verifier=None,
                 min_confidence: Optional[float] = None):
        self.llm = llm_client or DeepSeekClient()
        self._verifier = verifier
        self._min_confidence = min_confidence
        self._logger = get_logger("aeon.variants")

    def run(self, atom: Any, apparatus: Apparatus,
            work_hint: Optional[str] = None,
            trace_id: Optional[str] = None) -> VariantSelection:
        """Прогон по всем loci; ConfigError при work mismatch."""
        if work_hint:
            hint_tokens = work_tokens(work_hint)
            missing = sorted(token for token in work_tokens(apparatus.work)
                             if token not in hint_tokens)
            if missing:
                raise ConfigError(
                    f"apparatus work mismatch: '{apparatus.work}' против "
                    f"'{work_hint}' (не найдены токены: {missing}). "
                    f"Проверьте, что apparatus соответствует тексту."
                )

        selector = ReadingSelector(self.llm, self._get_verifier(),
                                   self._min_confidence)
        selections = [selector.select(locus, trace_id=trace_id)
                      for locus in apparatus.loci]
        total_calls = sum(selection.llm_calls for selection in selections)
        log_event(self._logger, "variants_done", work=apparatus.work,
                  loci=len(selections), llm_calls=total_calls, trace_id=trace_id)
        return VariantSelection(
            apparatus_version=apparatus.apparatus_version,
            work=apparatus.work,
            selections=selections,
            trace_id=trace_id,
            llm_calls=total_calls,
        )

    def _get_verifier(self):
        if self._verifier is None:
            from ..verification import VerificationEngine

            self._verifier = VerificationEngine(llm_client=self.llm)
        return self._verifier
