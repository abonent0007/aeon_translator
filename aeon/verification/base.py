"""
AEON Verification 2.0 — базовые типы.

Verdict — результат одного верификатора; VerificationContext — вход;
BaseVerifier — единый интерфейс `verify(context) -> Verdict` + структурный
лог каждого шага (trace_id связывает три агента одного атома).

Contract detective v1 (2.7.3): `build_claims(atom)` — semantic-only claims
с обязательным verbatim-якорем; meta/инструкции отсеиваются с событиями
`claim_skipped_meta` / `claim_no_anchor` (см. docs/contracts/detective_v1.md).
"""

import re
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..logging_config import get_logger, log_event
from .verdicts import (
    VERDICT_ABSTAINED,
    VERDICT_UNVERIFIABLE_MISSING_DATA,
)

# ── Contract v1: defensive-skip (meta/инструкции) ──
SKIP_PATTERNS = (
    re.compile(r"^(Intent|Domain|Type|Complexity|Urgency|Confidence):"),
    # Note 3 (куратор): $-альтернатива — bare-слово «Identify» без \s/: тоже skip
    re.compile(r"^(Identify|Recognize|Determine|Note|Find|Locate)(\s|:|$)"),
    re.compile(r"^Step \d+:"),
)
_ANCHOR_RUN_RE = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
_ANCHOR_MIN_LEN = 3
_ASCII_ANCHOR_MIN_LEN = 4


def _nfc(text: Any) -> str:
    return unicodedata.normalize("NFC", str(text or ""))


def is_meta_or_instruction(line: str) -> bool:
    """True для meta-строк («Intent: …») и инструкций («Identify …»)."""
    text = (line or "").strip()
    return any(pattern.match(text) for pattern in SKIP_PATTERNS)


def has_verbatim_anchor(claim: str, source: str) -> bool:
    """Есть ли в claim буквенная серия (≥3; ASCII — ≥4), входящая в source.

    NFC-сравнение обеих сторон (contract v1, Condition 2: якорь обязателен).
    """
    source_nfc = _nfc(source)
    for run in _ANCHOR_RUN_RE.findall(_nfc(claim)):
        if run.isascii():
            if len(run) < _ASCII_ANCHOR_MIN_LEN:
                continue
        elif len(run) < _ANCHOR_MIN_LEN:
            continue
        if run in source_nfc:
            return True
    return False


def build_claims(atom: Any, trace_id: Optional[str] = None) -> List[str]:
    """Semantic-only claims для верификации (contract v1).

    Отсеивает meta/инструкции (defensive-skip) и claims без verbatim-якоря;
    каждое отсечение — событие JSON-lines для аудита.
    """
    logger = get_logger("aeon.verification")
    source = getattr(atom, "source_text", "") or ""
    kept: List[str] = []
    for line in list(getattr(atom, "explanation_chain", []) or []):
        text = str(line).strip()
        if not text:
            continue
        if is_meta_or_instruction(text):
            log_event(logger, "claim_skipped_meta", row=text[:200],
                      reason="meta_or_instruction", trace_id=trace_id)
            continue
        if not has_verbatim_anchor(text, source):
            log_event(logger, "claim_no_anchor", row=text[:200],
                      reason="no_verbatim_anchor", trace_id=trace_id)
            continue
        kept.append(text)
    return kept


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
