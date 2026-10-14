"""
AEON Verification 2.0 — агент «Эксперт» (fact-checking).

Сверяет утверждения с внешними источниками (Wikidata через Entity Linking,
приоритет — уже связанные Entity из атома) и знаниями LLM.

ВАЖНО (стоп-точка 1.3 №2): недоступность источника (source_unavailable) →
`unverifiable_due_to_missing_data` (НЕЙТРАЛЬНО), НЕ `contradicted`.
Отсутствие данных ≠ опровержение.
"""

import json
from typing import Any, Dict, List, Optional

from .base import BaseVerifier, VerificationContext, Verdict
from .verdicts import VERDICT_CONTRADICTED, VERDICT_SUPPORTED

PROMPT_TEMPLATE = '''You are a fact-checking verifier ("Expert").
Use the EXTERNAL SOURCES data and your knowledge.

EXTERNAL SOURCES:
{SOURCES_BLOCK}

CLAIMS:
{CLAIMS_BLOCK}

Rules:
- For each claim choose status: "supported" (external data/knowledge confirm),
  "contradicted" (external data/knowledge refute), "unknown" (no data);
- "source": source id when supported/contradicted (e.g. "Q859"), else "";
- "confidence": 0.0-1.0; "reasoning": one short sentence.

Return ONLY valid JSON:
{"claims": [{"claim": "...", "status": "supported", "source": "Q859",
"confidence": 0.9, "reasoning": "..."}]}'''

_MAX_LINK_LOOKUPS = 3


def _build_prompt(sources: List[Dict[str, Any]], claims: List[str]) -> str:
    sources_block = (
        json.dumps(sources, ensure_ascii=False, indent=1) if sources else "нет внешних данных"
    )
    claims_block = "\n".join(f"- {claim}" for claim in claims)
    return (
        PROMPT_TEMPLATE
        .replace("{SOURCES_BLOCK}", sources_block)
        .replace("{CLAIMS_BLOCK}", claims_block)
    )


class ExpertAgent(BaseVerifier):
    """Fact-checking: внешние источники + знания LLM."""

    name = "expert"

    def __init__(self, llm, cfg, wikidata_client=None, logger_name: str = "aeon.verification"):
        super().__init__(llm, cfg, logger_name)
        self._wikidata = wikidata_client

    def verify(self, context: VerificationContext) -> Verdict:
        if not self.llm.available:
            return self._emit(context, self._abstained("LLM недоступен"))
        if not context.claims:
            return self._emit(context, self._neutral("нет утверждений для проверки", 0.5))

        external, unavailable = self._collect_external(context)
        if unavailable:
            return self._emit(context, self._neutral(
                "внешний источник недоступен (source_unavailable): данных нет, "
                "это не опровержение — нужны повторные попытки",
                0.4,
            ))

        prompt = _build_prompt(external, context.claims)
        result = self.llm._call_json([
            {"role": "system", "content": "You are a fact-checking verifier. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ], temperature=0.1)

        if result.get("parse_error") or not isinstance(result.get("claims"), list):
            return self._emit(context, self._abstained(
                f"невалидный ответ LLM: {result.get('parse_error', 'no claims key')}"
            ))

        rows = [row for row in result.get("claims", []) if isinstance(row, dict)]
        if not rows:
            return self._emit(context, self._neutral("LLM вернул пустой список утверждений", 0.3))

        contradicted: List[Dict[str, Any]] = []
        supported: List[Dict[str, Any]] = []
        sources: List[str] = []
        for row in rows:
            try:
                confidence = float(row.get("confidence", 0.5))
            except (TypeError, ValueError):
                confidence = 0.5
            normalized = {
                "claim": str(row.get("claim") or ""),
                "status": str(row.get("status") or "unknown"),
                "source": str(row.get("source") or ""),
                "confidence": confidence,
                "reasoning": str(row.get("reasoning") or ""),
            }
            if normalized["source"] and normalized["source"] not in sources:
                sources.append(normalized["source"])
            if normalized["status"] == "contradicted":
                contradicted.append(normalized)
            elif normalized["status"] == "supported":
                supported.append(normalized)

        details = {"claims": [dict(r) for r in rows if isinstance(r, dict)], "external": external}

        if contradicted:
            return self._emit(context, Verdict(
                verdict=VERDICT_CONTRADICTED,
                confidence=round(max(row["confidence"] for row in contradicted), 4),
                agent=self.name,
                reasoning=f"внешние источники опровергают {len(contradicted)} утверждение(й)",
                sources=sources,
                details=details,
            ))

        if not sources:
            sources = [str(value) for item in external for value in item.get("ids", {}).values()]

        if supported:
            avg_confidence = sum(row["confidence"] for row in supported) / len(supported)
            if len(sources) < self.cfg.min_sources:
                return self._emit(context, Verdict(
                    verdict="unverifiable_due_to_missing_data",
                    confidence=round(len(sources) / max(self.cfg.min_sources, 1), 4),
                    agent=self.name,
                    reasoning=(
                        f"подтверждений недостаточно: источников {len(sources)}, "
                        f"требуется ≥{self.cfg.min_sources}"
                    ),
                    sources=sources,
                    details=details,
                ))
            if avg_confidence < self.cfg.min_confidence:
                return self._emit(context, self._abstained(
                    f"fact-check confidence {avg_confidence:.2f} < {self.cfg.min_confidence}",
                    avg_confidence,
                ))
            return self._emit(context, Verdict(
                verdict=VERDICT_SUPPORTED,
                confidence=round(avg_confidence, 4),
                agent=self.name,
                reasoning=f"подтверждено внешними источниками ({len(sources)})",
                sources=sources,
                details=details,
            ))

        return self._emit(context, Verdict(
            verdict="unverifiable_due_to_missing_data",
            confidence=0.3,
            agent=self.name,
            reasoning="внешние данные не подтверждают и не опровергают утверждения",
            sources=sources,
            details=details,
        ))

    # ── внутреннее ──

    def _collect_external(self, context: VerificationContext):
        """Внешние источники: сначала entity_records, затем lookup по именам."""
        external: List[Dict[str, Any]] = []
        unavailable = False

        for record in context.entity_records:
            ids = getattr(record, "external_ids", None) or {}
            if ids:
                external.append({
                    "entity": getattr(record, "name", "") or "",
                    "ids": dict(ids),
                })

        if not external and self._wikidata is not None and context.entity_names:
            for name in context.entity_names[:_MAX_LINK_LOOKUPS]:
                link = self._wikidata.link_mention(name, language="en")
                if getattr(link, "source_unavailable", False):
                    unavailable = True
                    break
                if getattr(link, "entity", None) is not None:
                    external.append({
                        "entity": link.entity.label or name,
                        "ids": dict(link.external_ids or {}),
                    })

        return external, unavailable
