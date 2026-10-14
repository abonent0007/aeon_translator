"""
AEON Verification 2.0 — агент «Детектив» (source grounding).

Ищет ТОЧНЫЕ цитаты из источника для каждого утверждения.
`require_quote=True` (конфиг): «grounded» невозможен без непустой цитаты.
Промпт — один батч-вызов на все утверждения (производительность).
"""

from typing import List

from .base import BaseVerifier, VerificationContext, Verdict
from .verdicts import VERDICT_CONTRADICTED, VERDICT_GROUNDED

PROMPT_TEMPLATE = '''You are a source grounding verifier ("Detective").
For EACH claim check whether the SOURCE TEXT supports, contradicts, or lacks it.

SOURCE TEXT:
"{SOURCE}"

CLAIMS:
{CLAIMS_BLOCK}

Rules:
- "quote": an EXACT substring of SOURCE TEXT supporting the claim ("" if none);
- "contradicts": true ONLY if SOURCE TEXT directly contradicts the claim;
- "confidence": 0.0-1.0 (certainty of this per-claim judgement);
- "reasoning": one short sentence per claim.

Return ONLY valid JSON:
{"claims": [{"claim": "...", "quote": "...", "contradicts": false,
"confidence": 0.9, "reasoning": "..."}]}'''


def _build_prompt(source: str, claims: List[str]) -> str:
    claims_block = "\n".join(f"- {claim}" for claim in claims)
    return PROMPT_TEMPLATE.replace("{SOURCE}", source).replace("{CLAIMS_BLOCK}", claims_block)


class DetectiveAgent(BaseVerifier):
    """Source grounding: цитаты из исходного текста."""

    name = "detective"

    def verify(self, context: VerificationContext) -> Verdict:
        if not self.llm.available:
            return self._emit(context, self._abstained("LLM недоступен"))
        if not context.claims:
            return self._emit(context, self._neutral("нет утверждений для проверки", 0.5))

        prompt = _build_prompt(context.source_text, context.claims)
        result = self.llm._call_json([
            {"role": "system", "content": "You are a grounding verifier. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ], temperature=0.1)

        if result.get("parse_error") or not isinstance(result.get("claims"), list):
            return self._emit(context, self._abstained(
                f"невалидный ответ LLM: {result.get('parse_error', 'no claims key')}"
            ))

        rows = [row for row in result.get("claims", []) if isinstance(row, dict)]
        if not rows:
            return self._emit(context, self._neutral("LLM вернул пустой список утверждений", 0.3))

        per_claim = []
        grounded_count = 0
        for row in rows:
            quote = str(row.get("quote") or "").strip()
            contradicts = bool(row.get("contradicts"))
            try:
                confidence = float(row.get("confidence", 0.5))
            except (TypeError, ValueError):
                confidence = 0.5
            per_claim.append({
                "claim": str(row.get("claim") or ""),
                "quote": quote,
                "contradicts": contradicts,
                "confidence": confidence,
                "reasoning": str(row.get("reasoning") or ""),
            })
            if not contradicts and (quote or not self.cfg.require_quote):
                grounded_count += 1

        total = len(per_claim)
        details = {"claims": per_claim}
        contradicted = [row for row in per_claim if row["contradicts"]]

        if contradicted:
            return self._emit(context, Verdict(
                verdict=VERDICT_CONTRADICTED,
                confidence=round(max(row["confidence"] for row in contradicted), 4),
                agent=self.name,
                reasoning=f"источник противоречит {len(contradicted)}/{total} утверждениям",
                details=details,
            ))

        if grounded_count == total:
            avg_confidence = sum(row["confidence"] for row in per_claim) / total
            if avg_confidence < self.cfg.min_confidence:
                return self._emit(context, self._abstained(
                    f"grounding confidence {avg_confidence:.2f} < {self.cfg.min_confidence}",
                    avg_confidence,
                ))
            return self._emit(context, Verdict(
                verdict=VERDICT_GROUNDED,
                confidence=round(avg_confidence, 4),
                agent=self.name,
                reasoning=f"все {total} утверждений подтверждены точными цитатами",
                details=details,
            ))

        return self._emit(context, Verdict(
            verdict="unverifiable_due_to_missing_data",
            confidence=round(grounded_count / total, 4),
            agent=self.name,
            reasoning=(
                f"цитаты найдены для {grounded_count}/{total} утверждений — "
                f"нужны дополнительные источники"
            ),
            details=details,
        ))
