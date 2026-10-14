"""
AEON Variant Readings — селектор (шаг 3.5).

Порядок решений (0 LLM там, где можно):
  1. unanimous — все readings идентичны по тексту → 0 LLM,
     editions_support = union всех изданий, editions_vetoed = {};
  2. пустой context → no_selection_possible(reason="no_context");
  3. Detective pre-filter (режим `reading`, контекстное согласование):
     contradicted → vetoed (издания фиксируются в editions_vetoed);
     0 осталось → all_vetoed; 1 осталось → unanimous_after_veto (0 LLM);
  4. LLM-селектор (SELECT_READING_PROMPT, temp 0.0, editions СКРЫТЫ);
     chosen_index == -1 / parse_error / conf < порога → no_selection_possible.

Порог: AEON_VARIANTS_MIN_CONFIDENCE (default 0.5) — выбор среди
засвидетельствованного (риск ниже создания 0.75 в 2.3) и уже отфильтрован
Детективом.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..logging_config import get_logger, log_event
from ..verification import VerificationContext
from ..verification.verdicts import VERDICT_CONTRADICTED
from .apparatus import Locus, Reading
from .prompts import SELECT_READING_PROMPT


@dataclass
class Selection:
    locus: Locus
    chosen: Optional[Reading] = None
    confidence: float = 0.0
    reasoning: str = ""
    status: str = "no_selection_possible"
    editions_support: List[str] = field(default_factory=list)
    editions_vetoed: Dict[str, List[str]] = field(default_factory=dict)
    llm_calls: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "line": self.locus.line,
            "status": self.status,
            "chosen": ({"text": self.chosen.text, "editions": list(self.chosen.editions)}
                       if self.chosen else None),
            "confidence": round(float(self.confidence), 4),
            "reasoning": self.reasoning,
            "editions_support": list(self.editions_support),
            "editions_vetoed": {k: list(v) for k, v in self.editions_vetoed.items()},
            "llm_calls": self.llm_calls,
        }


class ReadingSelector:
    """Выбор одного reading для одного locus (никогда не генерирует текст)."""

    def __init__(self, llm, verifier, min_confidence: Optional[float] = None):
        self.llm = llm
        self._verifier = verifier
        if min_confidence is None:
            min_confidence = float(os.getenv("AEON_VARIANTS_MIN_CONFIDENCE", "0.5"))
        self.min_confidence = min_confidence
        self._logger = get_logger("aeon.variants")

    def select(self, locus: Locus, trace_id: Optional[str] = None) -> Selection:
        texts = [r.text.strip() for r in locus.readings]

        if len(set(texts)) == 1:
            support = sorted({e for r in locus.readings for e in r.editions})
            return self._emit(trace_id, Selection(
                locus=locus, chosen=locus.readings[0], confidence=1.0,
                reasoning="все чтения идентичны (различие только в изданиях)",
                status="unanimous", editions_support=support))

        if not (locus.context or "").strip():
            return self._emit(trace_id, Selection(
                locus=locus, reasoning="пустой контекст — нечем обосновывать выбор",
                status="no_selection_possible"))

        kept: List[Reading] = []
        vetoed: Dict[str, List[str]] = {}
        for reading in locus.readings:
            verdict = self._verifier.detective.verify(VerificationContext(
                source_text=locus.context,
                claims=[f"Attested reading {reading.text!r} is compatible "
                        f"with the surviving context"],
                mode="reading",
            ))
            if verdict.verdict == VERDICT_CONTRADICTED:
                vetoed[reading.text] = list(reading.editions)
            else:
                kept.append(reading)

        if not kept:
            return self._emit(trace_id, Selection(
                locus=locus, reasoning="все чтения отвергнуты Детективом",
                status="no_selection_possible", editions_vetoed=vetoed))

        if len(kept) == 1:
            return self._emit(trace_id, Selection(
                locus=locus, chosen=kept[0], confidence=1.0,
                reasoning="после veto осталось одно контекстно-согласованное чтение",
                status="unanimous_after_veto",
                editions_support=list(kept[0].editions), editions_vetoed=vetoed))

        if not self.llm.available:
            return self._emit(trace_id, Selection(
                locus=locus, reasoning="llm_unavailable",
                status="no_selection_possible", editions_vetoed=vetoed))

        numbered = "\n".join(f"{index}: {reading.text}"
                             for index, reading in enumerate(kept))
        prompt = (SELECT_READING_PROMPT
                  .replace("{CONTEXT}", locus.context)
                  .replace("{READINGS_NUMBERED}", numbered))
        data = self.llm._call_json([
            {"role": "system", "content": "You select among given readings. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ], temperature=0.0)

        if data.get("parse_error"):
            return self._emit(trace_id, Selection(
                locus=locus, reasoning=f"llm_parse_error: {data.get('parse_error')}",
                status="no_selection_possible", editions_vetoed=vetoed, llm_calls=1))

        try:
            index = int(data.get("chosen_index", -1))
        except (TypeError, ValueError):
            index = -1
        try:
            confidence = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        reasoning = str(data.get("reasoning") or "")

        if index == -1 or not (0 <= index < len(kept)):
            return self._emit(trace_id, Selection(
                locus=locus, confidence=0.0,
                reasoning=reasoning or "LLM воздержался (indeterminate)",
                status="no_selection_possible", editions_vetoed=vetoed, llm_calls=1))

        if confidence < self.min_confidence:
            return self._emit(trace_id, Selection(
                locus=locus, confidence=round(confidence, 4),
                reasoning=f"low_confidence: {reasoning}",
                status="no_selection_possible", editions_vetoed=vetoed, llm_calls=1))

        return self._emit(trace_id, Selection(
            locus=locus, chosen=kept[index], confidence=round(confidence, 4),
            reasoning=reasoning, status="selected",
            editions_support=list(kept[index].editions),
            editions_vetoed=vetoed, llm_calls=1))

    def _emit(self, trace_id: Optional[str], selection: Selection) -> Selection:
        log_event(self._logger, "variant_selection",
                  line=selection.locus.line, status=selection.status,
                  confidence=selection.confidence, trace_id=trace_id)
        return selection
