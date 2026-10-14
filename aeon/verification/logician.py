"""
AEON Verification 2.0 — агент «Логик» (semantic coherence).

Проверяет внутреннюю непротиворечивость набора утверждений.
`max_contradictions=0` (конфиг): любое противоречие → `incoherent` (негативно).
"""

from typing import List

from .base import BaseVerifier, VerificationContext, Verdict
from .verdicts import VERDICT_COHERENT, VERDICT_INCOHERENT

PROMPT_TEMPLATE = '''You are a coherence verifier ("Logician").
Check the CLAIMS for internal contradictions (claims that cannot all be true).

CLAIMS:
{CLAIMS_BLOCK}

Rules:
- "contradictions": list of {"a": claim, "b": claim, "explanation": "..."};
  empty list if none;
- "coherence": 0.0-1.0 (1.0 = fully consistent);
- "reasoning": one short sentence.

Return ONLY valid JSON:
{"contradictions": [], "coherence": 1.0, "reasoning": "..."}'''


def _build_prompt(claims: List[str]) -> str:
    claims_block = "\n".join(f"- {claim}" for claim in claims)
    return PROMPT_TEMPLATE.replace("{CLAIMS_BLOCK}", claims_block)


class LogicianAgent(BaseVerifier):
    """Semantic coherence: внутренняя непротиворечивость."""

    name = "logician"

    def verify(self, context: VerificationContext) -> Verdict:
        if not self.llm.available:
            return self._emit(context, self._abstained("LLM недоступен"))

        if len(context.claims) < 2:
            # False positive запрещён: без предмета сравнения coherence
            # не оценивается (abstained, не trivially coherent).
            return self._emit(context, self._abstained(
                "менее двух утверждений — coherence не оценивается (нет предмета сравнения)",
                0.0,
            ))

        result = self.llm._call_json([
            {"role": "system", "content": "You are a coherence verifier. Return only valid JSON."},
            {"role": "user", "content": _build_prompt(context.claims)},
        ], temperature=0.1)

        if result.get("parse_error"):
            return self._emit(context, self._abstained(
                f"невалидный ответ LLM: {result.get('parse_error')}"
            ))

        try:
            coherence = float(result.get("coherence", 0.0))
        except (TypeError, ValueError):
            coherence = 0.0

        contradictions = [
            item for item in (result.get("contradictions") or [])
            if isinstance(item, dict)
        ]
        details = {
            "coherence": round(coherence, 4),
            "contradictions": contradictions[:5],
        }

        if len(contradictions) > self.cfg.max_contradictions:
            return self._emit(context, Verdict(
                verdict=VERDICT_INCOHERENT,
                confidence=round(min(1.0, max(0.5, 1.0 - coherence)), 4),
                agent=self.name,
                reasoning=(
                    f"найдено противоречий: {len(contradictions)} "
                    f"(допустимо ≤{self.cfg.max_contradictions})"
                ),
                details=details,
            ))

        if coherence >= self.cfg.min_coherence:
            return self._emit(context, Verdict(
                verdict=VERDICT_COHERENT,
                confidence=round(coherence, 4),
                agent=self.name,
                reasoning="внутренних противоречий не найдено",
                details=details,
            ))

        return self._emit(context, self._abstained(
            f"coherence {coherence:.2f} < {self.cfg.min_coherence} — недостаточно для вывода",
            coherence,
        ))
