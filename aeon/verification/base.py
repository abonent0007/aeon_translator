"""
AEON Verification 2.0 — базовые типы.

Verdict — результат одного верификатора; VerificationContext — вход;
BaseVerifier — единый интерфейс `verify(context) -> Verdict` + структурный
лог каждого шага (trace_id связывает три агента одного атома).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..logging_config import get_logger, log_event
from .verdicts import (
    VERDICT_ABSTAINED,
    VERDICT_UNVERIFIABLE_MISSING_DATA,
)


@dataclass
class Verdict:
    """Результат одного верификатора."""

    verdict: str
    confidence: float
    agent: str
    reasoning: str = ""
    sources: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "confidence": round(float(self.confidence), 4),
            "agent": self.agent,
            "reasoning": self.reasoning,
            "sources": list(self.sources),
            "details": self.details,
        }


@dataclass
class VerificationContext:
    """Вход верификаторов: исходный текст, утверждения, сущности."""

    source_text: str
    claims: List[str] = field(default_factory=list)
    entity_names: List[str] = field(default_factory=list)
    entity_records: List[Any] = field(default_factory=list)  # Entity (v4.0)
    mode: str = "claim"   # "claim" (exact-quote) | "hypothesis" (context-agreement)
    trace_id: Optional[str] = None


class BaseVerifier(ABC):
    """Единый интерфейс агента-верификатора."""

    name = "base"

    def __init__(self, llm, cfg, logger_name: str = "aeon.verification"):
        self.llm = llm
        self.cfg = cfg
        self._logger = get_logger(logger_name)

    @abstractmethod
    def verify(self, context: VerificationContext) -> Verdict:
        """Проверка: возвращает Verdict (не бросает исключений)."""

    # ── helpers ──

    def _emit(self, context: VerificationContext, verdict: Verdict) -> Verdict:
        """Структурный лог шага (trace_id связывает агентов)."""
        log_event(
            self._logger,
            "verification_step",
            agent=self.name,
            verdict=verdict.verdict,
            confidence=round(float(verdict.confidence), 4),
            sources=list(verdict.sources),
            reasoning=(verdict.reasoning or "")[:200],
            trace_id=context.trace_id,
        )
        return verdict

    def _neutral(self, reasoning: str, confidence: float = 0.4) -> Verdict:
        return Verdict(
            verdict=VERDICT_UNVERIFIABLE_MISSING_DATA,
            confidence=confidence,
            agent=self.name,
            reasoning=reasoning,
        )

    def _abstained(self, reasoning: str, confidence: float = 0.0) -> Verdict:
        return Verdict(
            verdict=VERDICT_ABSTAINED,
            confidence=confidence,
            agent=self.name,
            reasoning=reasoning,
        )
