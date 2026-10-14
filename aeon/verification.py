"""
AEON Verification Engine — защита от галлюцинаций и проверка консистентности.
"""

import json
from typing import Dict, List, Tuple, Optional
from .llm_client import DeepSeekClient
from .embeddings import get_embedding_engine


class VerificationEngine:
    """
    Проверяет семантические атомы на:
    1. Консистентность (не противоречит ли сам себе)
    2. Фактическую обоснованность (опирается ли на исходный текст)
    3. Кросс-языковую согласованность (совпадает ли смысл на разных языках)
    """

    def __init__(self, llm_client: Optional[DeepSeekClient] = None):
        self.llm = llm_client or DeepSeekClient()
        self.embeddings = get_embedding_engine()
        self.checks_performed = 0
        self.hallucinations_caught = 0

    # ═══════════════════════════════════════════════════════════
    # Проверка консистентности
    # ═══════════════════════════════════════════════════════════

    def check_consistency(self, source_text: str, extracted_claims: List[str]) -> Dict:
        """
        Проверяет: все ли извлечённые утверждения согласуются с исходным текстом?
        Возвращает {score, flags, explanation}.
        """
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

        self.checks_performed += 1
        flags = result.get("contradictions", []) + result.get("unsupported", [])
        if flags:
            self.hallucinations_caught += 1

        return {
            "score": result.get("score", 1.0),
            "flags": flags,
            "explanation": result.get("explanation", "")
        }

    # ═══════════════════════════════════════════════════════════
    # Фактическая обоснованность (fact grounding)
    # ═══════════════════════════════════════════════════════════

    def check_fact_grounding(self, source_text: str, claim: str) -> Dict:
        """
        Проверяет: можно ли вывести утверждение из исходного текста?
        """
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

    # ═══════════════════════════════════════════════════════════
    # Кросс-языковая верификация
    # ═══════════════════════════════════════════════════════════

    def verify_cross_lingual(self, text_ru: str, text_en: str,
                              text_zh: Optional[str] = None) -> Dict:
        """
        Проверяет: совпадает ли смысл на разных языках?
        Использует LaBSE эмбеддинги + LLM для глубокой проверки.
        """
        result = {"aligned": True, "pairs": {}, "issues": []}

        # LaBSE similarity (быстрая проверка)
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

        # LLM глубокая проверка (если LaBSE показал расхождение)
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

    # ═══════════════════════════════════════════════════════════
    # Полная верификация атома
    # ═══════════════════════════════════════════════════════════

    def verify_atom(self, source_text: str, claims: List[str],
                    entities: List[str]) -> Dict:
        """
        Полный пайплайн верификации:
        консистентность + факт-граундинг + оценка риска галлюцинации.
        """
        result = {
            "consistency": {},
            "grounding": {},
            "hallucination_risk": 0.0,
            "overall_verdict": "unverified"
        }

        # 1. Консистентность
        result["consistency"] = self.check_consistency(source_text, claims)

        # 2. Факт-граундинг для каждого утверждения
        grounding_scores = []
        for claim in claims:
            g = self.check_fact_grounding(source_text, claim)
            result["grounding"][claim[:50]] = g
            grounding_scores.append(g.get("confidence", 0.5))

        # 3. Оценка риска галлюцинации
        consistency_score = result["consistency"].get("score", 1.0)
        avg_grounding = sum(grounding_scores) / len(grounding_scores) if grounding_scores else 0.5
        result["hallucination_risk"] = round(1.0 - (consistency_score * 0.5 + avg_grounding * 0.5), 3)

        # 4. Вердикт
        if result["hallucination_risk"] < 0.15:
            result["overall_verdict"] = "verified"
        elif result["hallucination_risk"] < 0.35:
            result["overall_verdict"] = "minor_issues"
        elif result["hallucination_risk"] < 0.6:
            result["overall_verdict"] = "suspect"
        else:
            result["overall_verdict"] = "likely_hallucination"

        return result

    def stats(self) -> dict:
        return {
            "checks_performed": self.checks_performed,
            "hallucinations_caught": self.hallucinations_caught,
            "prevention_rate": (
                self.hallucinations_caught / max(self.checks_performed, 1)
            )
        }
