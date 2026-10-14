"""
AEON Multi-focus — агрегатор (шаг 2.5).

НЕ разрешает противоречия между ролями (это фича: разные углы зрения
могут видеть разное). Флагует `all_disagree` эвристикой: две роли говорят
ОБ ОДНОМ предмете (высокое пересечение значимых слов), но формулировки
различаются. Семантический арбитраж (LLM) — backlog.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .base import FocusAnalysis, Insight


@dataclass
class MultiFocusResult:
    """Сводка нескольких ролей."""

    status: str  # "ok" | "llm_unavailable"
    roles: List[FocusAnalysis] = field(default_factory=list)
    insights_by_role: Dict[str, List[Insight]] = field(default_factory=dict)
    all_disagree: bool = False
    llm_calls: int = 0
    trace_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "roles": [analysis.to_dict() for analysis in self.roles],
            "insights_by_role": {
                role: [insight.to_dict() for insight in insights]
                for role, insights in self.insights_by_role.items()
            },
            "all_disagree": self.all_disagree,
            "llm_calls": self.llm_calls,
            "trace_id": self.trace_id,
        }


_WORD_RE = re.compile(r"[\wё]+", re.UNICODE)


def _tokens(claim: str) -> set:
    return {token for token in _WORD_RE.findall(claim.lower()) if len(token) > 3}


def _claims_conflict(claim_a: str, claim_b: str) -> bool:
    """Эвристика: тема одна (Jaccard ≥ 0.5 значимых слов), формулировки разные."""
    tokens_a = _tokens(claim_a)
    tokens_b = _tokens(claim_b)
    if not tokens_a or not tokens_b:
        return False
    union = tokens_a | tokens_b
    overlap = len(tokens_a & tokens_b) / len(union)
    return overlap >= 0.5 and claim_a.strip() != claim_b.strip()


def _roles_disagree(analyses: List[FocusAnalysis]) -> bool:
    for index, first in enumerate(analyses):
        for second in analyses[index + 1:]:
            for insight_a in first.insights:
                for insight_b in second.insights:
                    if _claims_conflict(insight_a.claim, insight_b.claim):
                        return True
    return False


def aggregate(analyses: List[FocusAnalysis],
              trace_id: Optional[str] = None) -> MultiFocusResult:
    """Сводка: сохраняет все insights, флагует расхождения, НЕ решает их."""
    insights_by_role = {analysis.role: analysis.insights for analysis in analyses}
    total_calls = sum(analysis.llm_calls for analysis in analyses)
    return MultiFocusResult(
        status="ok",
        roles=list(analyses),
        insights_by_role=insights_by_role,
        all_disagree=_roles_disagree(analyses),
        llm_calls=total_calls,
        trace_id=trace_id,
    )
