"""
AEON Linguistics — оркестратор Chain-of-Linguistics (шаг 2.4).

Порядок фиксирован: lexical → syntactic → semantic → pragmatic.
Зависимости строгие (ConfigError при нарушении):
  syntactic требует lexical; semantic — syntactic; pragmatic — semantic;
  lexical — standalone.

Halt-условие: confidence слоя < CONFIG.linguistics.layer_min_confidence →
статус `halted_at_<layer>`, частичный результат сохраняется.
Противоречия между слоями (стоп-точка 2.4 №2): вариант B — логируются
событием `layer_contradiction`, цепочка ПРОДОЛЖАЕТСЯ, confidence слоя
мягко понижается (×0.7); разрешение LLM (+1 вызов) — backlog.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..config import CONFIG, ConfigError, LinguisticsConfig
from ..llm_client import DeepSeekClient
from ..logging_config import get_logger, log_event
from .base import LayerContext, LayerResult
from .lexical import LexicalLayer
from .pragmatic import PragmaticLayer
from .semantic import SemanticLayer
from .syntactic import SyntacticLayer

PREREQUISITES = {
    "lexical": None,
    "syntactic": "lexical",
    "semantic": "syntactic",
    "pragmatic": "semantic",
}
#: kind-классы, по которым детектируются межслойные противоречия.
CONFLICT_KINDS = ("pos_tag", "role")
CONTRADICTION_CONFIDENCE_PENALTY = 0.7


@dataclass
class ChainResult:
    """Результат цепочки: слои + бюджет вызовов + статус."""

    status: str  # "ok" | "halted_at_<layer>" | "llm_unavailable"
    layers: List[LayerResult] = field(default_factory=list)
    llm_calls: int = 0
    trace_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "layers": [layer.to_dict() for layer in self.layers],
            "llm_calls": self.llm_calls,
            "trace_id": self.trace_id,
        }


def detect_contradictions(results: List[LayerResult]) -> List[Dict[str, Any]]:
    """Конфликты: один span + один kind-класс, разные значения из разных слоёв."""
    index: Dict[Any, Any] = {}
    conflicts: List[Dict[str, Any]] = []
    for result in results:
        for finding in result.findings:
            if finding.span is None or finding.kind not in CONFLICT_KINDS:
                continue
            key = (tuple(finding.span), finding.kind)
            previous = index.get(key)
            if previous is not None and previous[0].casefold() != finding.value.casefold():
                conflicts.append({
                    "span": list(finding.span),
                    "kind": finding.kind,
                    "layers": [previous[1], result.layer],
                    "values": [previous[0], finding.value],
                })
            else:
                index[key] = (finding.value, result.layer)
    return conflicts


class ChainOfLinguistics:
    """Оркестратор слоёв: валидация зависимостей, halt, трассировка."""

    def __init__(self, llm_client=None, config=None):
        full = config or CONFIG
        self.llm = llm_client or DeepSeekClient()
        self.cfg: LinguisticsConfig = full.linguistics
        self._logger = get_logger("aeon.linguistics")
        shared = {"llm": self.llm, "config": self.cfg}
        self._layers = {
            "lexical": LexicalLayer(**shared),
            "syntactic": SyntacticLayer(**shared),
            "semantic": SemanticLayer(**shared),
            "pragmatic": PragmaticLayer(**shared),
        }

    # ── публичное API ──

    def validate_layers(self, layers: List[str]) -> List[str]:
        """Строгая валидация зависимостей; возвращает канонический порядок."""
        requested = list(layers)
        unknown = [name for name in requested if name not in PREREQUISITES]
        if unknown:
            raise ConfigError(
                f"Неизвестные слои: {unknown}. Доступные: {list(PREREQUISITES)}"
            )
        requested_set = set(requested)
        for name in requested:
            prerequisite = PREREQUISITES[name]
            if prerequisite is not None and prerequisite not in requested_set:
                raise ConfigError(
                    f"Слой '{name}' требует '{prerequisite}' — добавьте его в layers "
                    f"(зависимости: syntactic→lexical, semantic→syntactic, "
                    f"pragmatic→semantic)."
                )
        canonical = [name for name in PREREQUISITES if name in requested_set]
        return canonical

    def run(self, normalized_text: str, *, original_text: Optional[str] = None,
            layers: Optional[List[str]] = None, pack=None,
            trace_id: Optional[str] = None) -> ChainResult:
        """Прогон цепочки; ConfigError при неверных layers."""
        requested = list(layers) if layers else list(PREREQUISITES)
        if "all" in requested:
            requested = list(PREREQUISITES)
        ordered = self.validate_layers(requested)

        if not self.llm.available:
            return ChainResult("llm_unavailable", [], 0, trace_id)

        results: List[LayerResult] = []
        previous: Optional[LayerResult] = None
        total_calls = 0
        for name in ordered:
            context = LayerContext(
                original_text=original_text or normalized_text,
                normalized_text=normalized_text,
                language_pack=pack,
                previous=previous,
                trace_id=trace_id,
            )
            result = self._layers[name].analyze(context)

            conflicts = detect_contradictions(results + [result])
            if conflicts:
                log_event(self._logger, "layer_contradiction",
                          layer=name, conflicts=conflicts, trace_id=trace_id)
                result.confidence = round(
                    result.confidence * CONTRADICTION_CONFIDENCE_PENALTY, 4
                )
                result.handoff["contradictions"] = conflicts

            results.append(result)
            total_calls += result.llm_calls
            if result.confidence < self.cfg.layer_min_confidence:
                return ChainResult(f"halted_at_{name}", results, total_calls, trace_id)
            previous = result

        log_event(self._logger, "chain_done", status="ok", layers=len(results),
                  llm_calls=total_calls, trace_id=trace_id)
        return ChainResult("ok", results, total_calls, trace_id)
