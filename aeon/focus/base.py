"""
AEON Multi-focus — базовая структура (шаг 2.5).

FocusRole — независимая роль-аналитик; роли НЕ видят результатов друг
друга (только исходный Atom + пак + linguistic layers): «заражение»
исключено структурно (FocusContext не содержит чужих выводов).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..logging_config import get_logger, log_event


@dataclass
class Insight:
    """Семантическое наблюдение роли."""

    claim: str
    angle: str = ""                    # "historical_context" | "philosophical" | ...
    confidence: float = 0.5
    source_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim": self.claim,
            "angle": self.angle,
            "confidence": round(float(self.confidence), 4),
            "source_refs": list(self.source_refs),
        }


@dataclass
class FocusAnalysis:
    """Результат одной роли."""

    role: str
    insights: List[Insight] = field(default_factory=list)
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    llm_calls: int = 1
    trace_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "insights": [insight.to_dict() for insight in self.insights],
            "confidence": round(float(self.confidence), 4),
            "evidence": list(self.evidence),
            "llm_calls": self.llm_calls,
            "trace_id": self.trace_id,
        }


@dataclass
class FocusContext:
    """Вход роли. ВАЖНО: никаких результатов других ролей (только общий вход)."""

    atom: Any = None
    language_pack: Any = None
    linguistic_layers: Any = None      # ChainResult | None
    trace_id: Optional[str] = None


class FocusRole(ABC):
    """Контракт роли: analyze(context) -> FocusAnalysis."""

    name: str = "base"
    angle: str = "general"

    def __init__(self, llm, config=None, logger_name: str = "aeon.focus"):
        self.llm = llm
        self.cfg = config
        self._logger = get_logger(logger_name)

    @abstractmethod
    def analyze(self, context: FocusContext) -> FocusAnalysis:
        ...

    def _analyze_json(self, context: FocusContext, template: str) -> FocusAnalysis:
        if not self.llm.available:
            return self._abstained(context, "llm_unavailable")
        prompt = self._build_prompt(template, context)
        data = self.llm._call_json([
            {"role": "system", "content": "You are a focused analyst of ancient texts. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ], temperature=0.0)
        if data.get("parse_error"):
            return self._abstained(context, f"parse_error: {data.get('parse_error')}")

        insights = self._parse_insights(data.get("insights") or [])
        try:
            confidence = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        analysis = FocusAnalysis(
            role=self.name,
            insights=insights,
            confidence=round(min(1.0, max(0.0, confidence)), 4),
            evidence=[str(item) for item in (data.get("evidence") or [])],
            llm_calls=1,
            trace_id=context.trace_id,
        )
        log_event(self._logger, "role_done", role=self.name,
                  insights=len(insights), confidence=analysis.confidence,
                  trace_id=context.trace_id)
        return analysis

    def _build_prompt(self, template: str, context: FocusContext) -> str:
        prompt = template
        atom = context.atom
        source_text = getattr(atom, "source_text", "") if atom is not None else ""
        prompt += "\n\nTEXT UNDER ANALYSIS:\n" + source_text[:4000]
        entities = getattr(atom, "entities", None) or []
        if entities:
            entity_lines = []
            for entity in entities[:10]:
                external = getattr(entity, "external_ids", None) or {}
                suffix = f" {external}" if external else ""
                entity_lines.append(f"- {getattr(entity, 'name', '?')}{suffix}")
            prompt += "\n\nENTITIES:\n" + "\n".join(entity_lines)
        if context.linguistic_layers is not None:
            handoffs = {
                layer.layer: layer.handoff
                for layer in getattr(context.linguistic_layers, "layers", [])
            }
            import json
            prompt += ("\n\nLINGUISTIC LAYERS SUMMARY:\n"
                       + json.dumps(handoffs, ensure_ascii=False)[:1200])
        return prompt

    def _parse_insights(self, raw_insights: List[Any]) -> List[Insight]:
        insights: List[Insight] = []
        for item in raw_insights:
            if not isinstance(item, dict):
                continue
            claim = str(item.get("claim") or "").strip()
            if not claim:
                continue
            try:
                confidence = float(item.get("confidence", 0.5))
            except (TypeError, ValueError):
                confidence = 0.5
            insights.append(Insight(
                claim=claim,
                angle=str(item.get("angle") or self.angle),
                confidence=min(1.0, max(0.0, confidence)),
                source_refs=[str(ref) for ref in (item.get("source_refs") or [])],
            ))
        return insights

    def _abstained(self, context: FocusContext, reason: str) -> FocusAnalysis:
        log_event(self._logger, "role_abstained", role=self.name,
                  reason=reason, trace_id=context.trace_id)
        return FocusAnalysis(role=self.name, confidence=0.0, llm_calls=0,
                             evidence=[reason], trace_id=context.trace_id)
