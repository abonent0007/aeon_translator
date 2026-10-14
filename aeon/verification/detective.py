"""
AEON Verification 2.0 — агент «Детектив» (source grounding).

Ищет ТОЧНЫЕ цитаты из источника для каждого утверждения.
`require_quote=True` (конфиг): «grounded» невозможен без непустой цитаты.
Промпт — один батч-вызов на все утверждения (производительность).
"""

from typing import List

from ..logging_config import log_event
from .base import (
    BaseVerifier,
    VerificationContext,
    Verdict,
    _nfc,
    is_meta_or_instruction,
)
from .verdicts import VERDICT_CONTRADICTED, VERDICT_GROUNDED

_MIN_QUOTE_LEN = 3  # contract v1: короткие «цитаты» не считаются grounded

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


HYPOTHESIS_PROMPT_TEMPLATE = '''You are a source grounding verifier ("Detective").
For EACH candidate restoration check whether the SURVIVING CONTEXT
supports it or at least does not contradict it.

SURVIVING SOURCE TEXT:
"{SOURCE}"

CANDIDATES:
{CLAIMS_BLOCK}

Rules:
- "contradicts": true ONLY if the surviving context makes the candidate
  impossible (conflicting words, grammar or facts in preserved text);
- "quote": the CLOSEST surviving-context fragment (EXACT substring)
  speaking for/against the candidate ("" if the context is silent);
- "confidence": 0.0-1.0; "reasoning": one short sentence.

Return ONLY valid JSON:
{"claims": [{"claim": "...", "quote": "...", "contradicts": false,
"confidence": 0.9, "reasoning": "..."}]}'''


def _build_prompt(source: str, claims: List[str],
                  template: str = PROMPT_TEMPLATE) -> str:
    claims_block = "\n".join(f"- {claim}" for claim in claims)
    return template.replace("{SOURCE}", source).replace("{CLAIMS_BLOCK}", claims_block)


class DetectiveAgent(BaseVerifier):
    """Source grounding: exact-quote (claim) / context-agreement (hypothesis)."""

    name = "detective"

    def verify(self, context: VerificationContext,
               mode: str = "") -> Verdict:
        """
        Два режима промпта (curator fix 2.3):
          - claim      — exact-quote: точная подстрока из SOURCE;
          - hypothesis — context-agreement: согласованность кандидата
            с СОХРАНИВШИМСЯ контекстом (exact-quote утраченного невозможен).
        Режим берётся из mode-аргумента или context.mode (default "claim").
        Третий семантический режим "reading" (шаг 3.5, variant readings):
        контекстное согласование кандидата-чтения с сохранившимся контекстом —
        использует тот же шаблон, что "hypothesis".
        """
        selected_mode = mode or getattr(context, "mode", "claim")
        if not self.llm.available:
            return self._emit(context, self._abstained("LLM недоступен"))
        if not context.claims:
            return self._emit(context, self._neutral("нет утверждений для проверки", 0.5))

        # Contract v1 (2.7.3): defensive-skip meta/инструкций — вторая линия
        if selected_mode == "claim":
            semantic_claims = [c for c in context.claims
                               if not is_meta_or_instruction(str(c))]
            for skipped in context.claims:
                if is_meta_or_instruction(str(skipped)):
                    log_event(self._logger, "claim_skipped_meta",
                              row=str(skipped)[:200],
                              reason="detective_input_filter",
                              trace_id=context.trace_id)
            if not semantic_claims:
                log_event(self._logger, "detective_no_semantic_claims",
                          trace_id=context.trace_id)
                return self._emit(context, self._neutral(
                    "no_semantic_claims: все claims — meta/инструкции "
                    "(дефект extractor?)", 0.3))
        else:  # hypothesis/reading: конструируемые claims не фильтруем по regex
            semantic_claims = list(context.claims)

        template = (HYPOTHESIS_PROMPT_TEMPLATE
                    if selected_mode in ("hypothesis", "reading")
                    else PROMPT_TEMPLATE)
        prompt = _build_prompt(context.source_text, semantic_claims, template)
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

        source_nfc = _nfc(context.source_text)
        per_claim = []
        grounded_count = 0
        hallucinated = 0
        for row in rows:
            quote = str(row.get("quote") or "").strip()
            contradicts = bool(row.get("contradicts"))
            try:
                confidence = float(row.get("confidence", 0.5))
            except (TypeError, ValueError):
                confidence = 0.5
            grounded = False
            if not contradicts:
                if quote and len(quote) >= _MIN_QUOTE_LEN and _nfc(quote) in source_nfc:
                    grounded = True
                elif quote:
                    # Contract v1 (Q2): непустой quote, но НЕ подстрока source —
                    # галлюцинация цитаты: событие + строка НЕ grounded
                    hallucinated += 1
                    log_event(self._logger, "detective_quote_not_in_source",
                              quote=quote[:160],
                              claim=str(row.get("claim") or "")[:160],
                              trace_id=context.trace_id)
            if grounded:
                grounded_count += 1
            per_claim.append({
                "claim": str(row.get("claim") or ""),
                "quote": quote,
                "contradicts": contradicts,
                "confidence": confidence,
                "grounded": grounded,
                "reasoning": str(row.get("reasoning") or ""),
            })

        total = len(per_claim)
        details = {"claims": per_claim, "hallucinated_quotes": hallucinated}
        contradicted = [row for row in per_claim if row["contradicts"]]

        if contradicted:
            return self._emit(context, Verdict(
                verdict=VERDICT_CONTRADICTED,
                confidence=round(max(row["confidence"] for row in contradicted), 4),
                agent=self.name,
                reasoning=f"источник противоречит {len(contradicted)}/{total} утверждениям",
                details=details,
            ))

        ratio = round(grounded_count / total, 4)
        avg_confidence = sum(row["confidence"] for row in per_claim) / total

        if ratio == 1.0:
            # полное покрытие: сохраняем min_confidence-гейт (Q3 — порог не меняем)
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

        if ratio >= self.cfg.grounded_ratio_threshold:
            # Contract v1 (Q1): частичное покрытие — пониженная уверенность
            return self._emit(context, Verdict(
                verdict=VERDICT_GROUNDED,
                confidence=round(ratio * avg_confidence, 4),
                agent=self.name,
                reasoning=(
                    f"grounded {grounded_count}/{total} "
                    f"(ratio {ratio:.2f} ≥ {self.cfg.grounded_ratio_threshold}) — "
                    f"пониженная уверенность"
                ),
                details=details,
            ))

        return self._emit(context, Verdict(
            verdict="unverifiable_due_to_missing_data",
            confidence=ratio,
            agent=self.name,
            reasoning=(
                f"цитаты найдены для {grounded_count}/{total} утверждений — "
                f"нужны дополнительные источники"
            ),
            details=details,
        ))
