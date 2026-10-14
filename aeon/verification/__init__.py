"""
AEON Verification 2.0 — пакет верификации.

Публичное API:
    VerificationEngine — фасад (обратная совместимость v3.0: verify_atom,
        check_consistency, check_fact_grounding, verify_cross_lingual, stats)
        + новый 3-агентный пайплайн (Детектив / Эксперт / Логик) с CVI
        и калиброванным воздержанием.
    Агенты: DetectiveAgent, ExpertAgent, LogicianAgent.
    Агрегатор: Aggregator, CombinedVerdict.
    Типы: Verdict, VerificationContext, BaseVerifier.
"""

from typing import Dict, List, Optional

from ..config import CONFIG
from ..embeddings import get_embedding_engine
from ..llm_client import DeepSeekClient
from .aggregator import Aggregator, CombinedVerdict
from .base import (
    BaseVerifier,
    Verdict,
    VerificationContext,
    build_claims,
    has_verbatim_anchor,
    is_meta_or_instruction,
)
from .detective import DetectiveAgent
from .expert import ExpertAgent
from .logician import LogicianAgent
from .verdicts import (
    ABSTAINED_VERDICTS,
    ALL_VERDICTS,
    NEGATIVE_VERDICTS,
    NEUTRAL_VERDICTS,
    POSITIVE_VERDICTS,
    VERDICT_ABSTAINED,
    VERDICT_COHERENT,
    VERDICT_CONTRADICTED,
    VERDICT_GROUNDED,
    VERDICT_INCOHERENT,
    VERDICT_NEEDS_REVIEW,
    VERDICT_SUPPORTED,
    VERDICT_UNVERIFIABLE_MISSING_DATA,
    VERDICT_VERIFIED,
    is_abstained,
    is_negative,
    is_neutral,
    is_positive,
)

__all__ = [
    "VerificationEngine",
    "DetectiveAgent",
    "ExpertAgent",
    "LogicianAgent",
    "Aggregator",
    "CombinedVerdict",
    "Verdict",
    "build_claims",
    "has_verbatim_anchor",
    "is_meta_or_instruction",
    "VerificationContext",
    "BaseVerifier",
]


class VerificationEngine:
    """
    Верификация атомов: три независимых агента + CVI-агрегатор.

    Новый пайплайн (verify_atom):
      1. Детектив  — точные цитаты из источника (grounding);
      2. Эксперт   — внешний факт-чек (Wikidata + знания LLM);
      3. Логик     — внутренняя непротиворечивость.
    Агрегатор: negatives доминируют; calibrated abstention («Я не знаю»).
    Возвращает legacy-ключи v3.0 (consistency/grounding/hallucination_risk/
    overall_verdict) И v4.0-ключи (agents/combined/cvi/abstained/
    reasoning_trace).
    """

    def __init__(self, llm_client: Optional[DeepSeekClient] = None,
                 *, wikidata_client=None, config=None):
        full = config or CONFIG
        self.llm = llm_client or DeepSeekClient()
        self.embeddings = get_embedding_engine()
        self.cfg = full.verification
        self.legacy_cfg = full.legacy_verification
        self.detective = DetectiveAgent(self.llm, self.cfg.detective)
        self.expert = ExpertAgent(self.llm, self.cfg.expert, wikidata_client=wikidata_client)
        self.logician = LogicianAgent(self.llm, self.cfg.logician)
        self.aggregator = Aggregator(
            self.cfg, review_threshold=1.0 - self.legacy_cfg.risk_verified_max
        )
        self.checks_performed = 0
        self.hallucinations_caught = 0

    # ═══════════════════════════════════════════════════════════
    # Новый пайплайн (Verification 2.0) + legacy-проекция
    # ═══════════════════════════════════════════════════════════

    def verify_atom(self, source_text: str, claims: List[str],
                    entities: List[str], trace_id: Optional[str] = None,
                    mode: str = "full") -> Dict:
        """
        Верификация атома: Детектив + (Эксперт) + Логик → CVI.

        mode: "basic" — Детектив + Логик (без внешних источников);
              "full"  — все три агента (+ Wikidata).
        Совместим с v3.0: возвращает consistency/grounding/
        hallucination_risk/overall_verdict (+ новые ключи).
        """
        clean_claims = [c for c in (claims or []) if isinstance(c, str) and c.strip()]
        entity_names = [
            e if isinstance(e, str) else getattr(e, "name", str(e))
            for e in (entities or [])
        ]
        context = VerificationContext(
            source_text=source_text,
            claims=clean_claims,
            entity_names=entity_names,
            trace_id=trace_id,
        )

        verdicts: Dict[str, Verdict] = {"detective": self.detective.verify(context)}
        if mode == "full":
            verdicts["expert"] = self.expert.verify(context)
        verdicts["logician"] = self.logician.verify(context)
        combined = self.aggregator.combine(verdicts)

        self.checks_performed += 1
        if combined.verdict == VERDICT_CONTRADICTED:
            self.hallucinations_caught += 1

        # ── legacy-проекция v3.0 ──
        if combined.abstained:
            all_conf = [float(v.confidence) for v in verdicts.values()]
            risk = round(1.0 - (sum(all_conf) / len(all_conf) if all_conf else 0.0), 3)
        else:
            risk = round(1.0 - combined.overall_confidence, 3)

        if risk < self.legacy_cfg.risk_verified_max:
            legacy_verdict = "verified"
        elif risk < self.legacy_cfg.risk_minor_max:
            legacy_verdict = "minor_issues"
        elif risk < self.legacy_cfg.risk_suspect_max:
            legacy_verdict = "suspect"
        else:
            legacy_verdict = "likely_hallucination"
        if combined.abstained:
            legacy_verdict = "unverified"

        flags = [
            f"{name}: {v.reasoning}"
            for name, v in verdicts.items()
            if (is_negative(v.verdict) or is_neutral(v.verdict)) and v.reasoning
        ]

        grounding: Dict[str, Dict] = {}
        for row in verdicts["detective"].details.get("claims", []):
            key = str(row.get("claim", ""))[:50]
            grounding[key] = {
                "grounded": bool(row.get("quote")) and not row.get("contradicts", False),
                "confidence": float(row.get("confidence", 0.5)),
                "evidence": row.get("quote", ""),
                "reasoning": row.get("reasoning", ""),
            }

        return {
            # legacy v3.0
            "consistency": {
                "score": combined.overall_confidence,
                "flags": flags,
                "explanation": f"combined: {combined.verdict}",
            },
            "grounding": grounding,
            "hallucination_risk": risk,
            "overall_verdict": legacy_verdict,
            # v4.0 Verification 2.0
            "agents": {name: v.to_dict() for name, v in verdicts.items()},
            "combined": combined.to_dict(),
            "cvi": combined.overall_confidence,
            "abstained": combined.abstained,
            "reasoning_trace": combined.reasoning_trace,
        }

    # ═══════════════════════════════════════════════════════════
    # Legacy-методы v3.0 (сохранены для обратной совместимости)
    # ═══════════════════════════════════════════════════════════

    def check_consistency(self, source_text: str, extracted_claims: List[str]) -> Dict:
        """v3.0: все ли утверждения согласуются с исходным текстом."""
        if not self.llm.available or not extracted_claims:
            return {"score": 1.0, "flags": [], "explanation": "no LLM / no claims"}

        prompt = f"""You are a semantic consistency verifier. Check if ALL claims below are consistent with the source text.

SOURCE TEXT: "{source_text}"

EXTRACTED CLAIMS:
{chr(10).join(f"- {c}" for c in extracted_claims)}

Return ONLY valid JSON:
{{
    "score": float 0-1 (1=all consistent),
    "contradictions": list of strings (any claim that contradicts the source),
    "unsupported": list of strings (claims not supported by source),
    "explanation": brief summary
}}"""

        result = self.llm._call_json([
            {"role": "system", "content": "You are a consistency verifier. Return only valid JSON."},
            {"role": "user", "content": prompt}
        ], temperature=0.1)

        flags = result.get("contradictions", []) + result.get("unsupported", [])
        if flags:
            self.hallucinations_caught += 1

        return {
            "score": result.get("score", 1.0),
            "flags": flags,
            "explanation": result.get("explanation", "")
        }

    def check_fact_grounding(self, source_text: str, claim: str) -> Dict:
        """v3.0: можно ли вывести утверждение из исходного текста."""
        if not self.llm.available:
            return {"grounded": True, "confidence": 0.5, "evidence": ""}

        prompt = f"""Verify if this claim can be directly inferred from the source text.

SOURCE: "{source_text}"
CLAIM: "{claim}"

Return ONLY valid JSON:
{{
    "grounded": true/false,
    "confidence": float 0-1,
    "evidence": "exact quote from source that supports the claim, or empty string",
    "reasoning": "one-sentence explanation"
}}"""

        result = self.llm._call_json([
            {"role": "system", "content": "You verify factual grounding. Return only valid JSON."},
            {"role": "user", "content": prompt}
        ], temperature=0.1)

        if not result.get("grounded", True):
            self.hallucinations_caught += 1

        return result

    def verify_cross_lingual(self, text_ru: str, text_en: str,
                              text_zh: Optional[str] = None) -> Dict:
        """v3.0: совпадает ли смысл на разных языках (эмбеддинги + LLM)."""
        result = {"aligned": True, "pairs": {}, "issues": []}

        if self.embeddings.available:
            sim = self.embeddings.similarity(text_ru, text_en)
            result["pairs"]["ru-en"] = {"similarity": round(sim, 4),
                                         "status": "aligned" if sim > 0.65 else "check_needed"}
            if sim < 0.65:
                result["issues"].append(f"ru-en low similarity: {sim:.3f}")
                result["aligned"] = False

            if text_zh:
                sim_ru_zh = self.embeddings.similarity(text_ru, text_zh)
                sim_en_zh = self.embeddings.similarity(text_en, text_zh)
                result["pairs"]["ru-zh"] = {"similarity": round(sim_ru_zh, 4)}
                result["pairs"]["en-zh"] = {"similarity": round(sim_en_zh, 4)}
                if sim_ru_zh < 0.65:
                    result["issues"].append(f"ru-zh low similarity: {sim_ru_zh:.3f}")
                    result["aligned"] = False

        if result["issues"] and self.llm.available:
            llm_check = self._llm_cross_lingual_check(text_ru, text_en, text_zh)
            result["llm_verdict"] = llm_check

        return result

    def _llm_cross_lingual_check(self, text_ru: str, text_en: str,
                                  text_zh: Optional[str] = None) -> Dict:
        prompt = f"""Compare these texts and check if they express the SAME meaning:

Russian: "{text_ru}"
English: "{text_en}" """
        if text_zh:
            prompt += f'\nChinese: "{text_zh}"'

        prompt += """

Return ONLY valid JSON:
{
    "same_meaning": true/false,
    "semantic_overlap": float 0-1,
    "differences": ["list of any meaning differences"],
    "verdict": "one sentence summary"
}"""
        return self.llm._call_json([
            {"role": "system", "content": "You verify cross-lingual meaning equivalence."},
            {"role": "user", "content": prompt}
        ], temperature=0.1)

    def stats(self) -> dict:
        return {
            "checks_performed": self.checks_performed,
            "hallucinations_caught": self.hallucinations_caught,
            "prevention_rate": (
                self.hallucinations_caught / max(self.checks_performed, 1)
            )
        }
