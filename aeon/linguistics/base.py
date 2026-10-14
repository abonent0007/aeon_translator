"""
AEON Linguistics — базовая структура Chain-of-Linguistics (шаг 2.4).

Слои: lexical → syntactic → semantic → pragmatic (порядок фиксирован).
Каждый слой получает LayerContext (исходный текст + normalized_text +
previous LayerResult) и возвращает LayerResult с типизированными Finding.
"""

import json
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..logging_config import get_logger, log_event


@dataclass
class Finding:
    """Типизированная находка слоя."""

    kind: str                       # lemma | pos_tag | morph | dependency | role | proposition | speech_act | ...
    value: str
    span: Optional[Tuple[int, int]] = None   # offset в normalized_text
    confidence: float = 0.5
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "value": self.value,
            "span": list(self.span) if self.span else None,
            "confidence": round(float(self.confidence), 4),
            "note": self.note,
        }


@dataclass
class LayerResult:
    """Результат одного слоя (handoff — контракт с следующим слоем)."""

    layer: str
    findings: List[Finding] = field(default_factory=list)
    confidence: float = 0.0
    handoff: Dict[str, Any] = field(default_factory=dict)
    llm_calls: int = 1
    trace_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer": self.layer,
            "findings": [finding.to_dict() for finding in self.findings],
            "confidence": round(float(self.confidence), 4),
            "handoff": self.handoff,
            "llm_calls": self.llm_calls,
            "trace_id": self.trace_id,
        }


@dataclass
class LayerContext:
    """Вход слоя: текст, пак, выход предыдущего слоя, trace_id."""

    original_text: str
    normalized_text: str = ""
    language_pack: Any = None            # LanguagePack | None (без циклов импорта)
    previous: Optional[LayerResult] = None
    trace_id: Optional[str] = None


class LinguisticLayer(ABC):
    """Контракт слоя: analyze(context) -> LayerResult (не бросает исключений)."""

    name: str = "base"

    def __init__(self, llm, config=None, logger_name: str = "aeon.linguistics"):
        self.llm = llm
        self.cfg = config
        self._logger = get_logger(logger_name)

    @abstractmethod
    def analyze(self, context: LayerContext) -> LayerResult:
        ...

    # ── общая механика для подклассов ──

    def _analyze_json(self, context: LayerContext, template: str) -> LayerResult:
        """LLM-вызов слоя (temp 0.0) + разбор findings/confidence/handoff."""
        if not self.llm.available:
            return self._abstained(context, "llm_unavailable")
        prompt = self._prompt_with_hints(template, context)
        data = self.llm._call_json([
            {"role": "system", "content": "You are a linguistic analyst. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ], temperature=0.0)
        if data.get("parse_error"):
            return self._abstained(context, f"parse_error: {data.get('parse_error')}")

        findings = self._parse_findings(data.get("findings") or [])
        try:
            confidence = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = min(1.0, max(0.0, confidence))
        result = LayerResult(
            layer=self.name,
            findings=findings,
            confidence=round(confidence, 4),
            handoff=dict(data.get("handoff") or {}),
            llm_calls=1,
            trace_id=context.trace_id,
        )
        return self._emit(context, result)

    def _prompt_with_hints(self, template: str, context: LayerContext) -> str:
        prompt = template
        hints = None
        pack = context.language_pack
        if pack is not None and hasattr(pack, "linguistic_hints"):
            hints = pack.linguistic_hints(self.name)
        if hints:
            prompt += "\n\nLANGUAGE-SPECIFIC HINTS:\n" + hints
        if context.previous is not None:
            previous_handoff = json.dumps(context.previous.handoff, ensure_ascii=False)
            if len(previous_handoff) > 1500:
                log_event(
                    self._logger, "handoff_truncated",
                    layer=self.name, from_layer=context.previous.layer,
                    original_len=len(previous_handoff), trace_id=context.trace_id,
                )
                previous_handoff = previous_handoff[:1500]
            prompt += (
                f"\n\nPREVIOUS LAYER OUTPUT ({context.previous.layer}):\n"
                + previous_handoff
            )
        text = context.normalized_text or context.original_text
        return prompt + "\n\nTEXT UNDER ANALYSIS:\n" + text

    @staticmethod
    def _parse_findings(raw_findings: List[Any]) -> List[Finding]:
        findings: List[Finding] = []
        for item in raw_findings:
            if not isinstance(item, dict):
                continue
            span = item.get("span")
            normalized_span = None
            if isinstance(span, (list, tuple)) and len(span) == 2:
                try:
                    normalized_span = (int(span[0]), int(span[1]))
                except (TypeError, ValueError):
                    normalized_span = None
            try:
                confidence = float(item.get("confidence", 0.5))
            except (TypeError, ValueError):
                confidence = 0.5
            findings.append(Finding(
                kind=str(item.get("kind") or "unknown"),
                value=str(item.get("value") or ""),
                span=normalized_span,
                confidence=min(1.0, max(0.0, confidence)),
                note=str(item.get("note") or ""),
            ))
        return findings

    def _emit(self, context: LayerContext, result: LayerResult) -> LayerResult:
        log_event(self._logger, "layer_done", layer=self.name,
                  confidence=result.confidence, findings=len(result.findings),
                  trace_id=context.trace_id)
        return result

    def _abstained(self, context: LayerContext, reason: str) -> LayerResult:
        return self._emit(context, LayerResult(
            layer=self.name, confidence=0.0, llm_calls=0,
            handoff={"reason": reason}, trace_id=context.trace_id,
        ))
