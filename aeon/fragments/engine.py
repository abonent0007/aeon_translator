"""
AEON Fragment Hypothesis Engine (шаг 2.3) — гипотезы восстановления.

Поток:
  1. маркеры: `pack.detect_markers` (приоритет) либо fallback
     `semantic_atom.LACUNA_MARKERS` (текст без пака);
  2. `fragment_density = markers_count / max(len(text), 1)`;
  3. cruces (`†…†`) — loci desperati: НЕ восстанавливаются без внешних
     свидетельств; если среди маркеров нет ничего, кроме cruces →
     `no_reconstruction_possible(reason="cruces_without_external_evidence")`
     без LLM-вызова (стоп-точка 2.3 №4);
  4. LLM-реконструкция (`pack.prompts["reconstruct"]` или
     DEFAULT_RECONSTRUCT_PROMPT): 2–4 гипотезы; серверная защита —
     cap `max_hypotheses`, `max(confidence) < min_confidence` →
     `no_reconstruction_possible(reason="max_confidence_below_threshold")`;
  5. верификация (`verify_hypotheses=True`, стоп-точка 2.3 №2): каждая
     гипотеза → Detective (N вызовов); contradicted → отбрасывается;
     пусто → `no_reconstruction_possible(reason="all_contradicted")`.

`no_reconstruction_possible` — ТЕРМИНАЛЬНЫЙ вердикт прогона; `reason` —
структурированный сигнал для внешних источников (Pleiades/Trismegistos, Ф2.6).
Варианты чтения (contested readings ≠ лакуны) — backlog Ф2.4+ (стоп-точка №1).
"""

from typing import List, Optional

from ..config import CONFIG, FragmentsConfig
from ..llm_client import DeepSeekClient
from ..logging_config import get_logger, log_event
from ..semantic_atom import SemanticAtom
from .hypothesis import Hypothesis, NoReconstruction, ReconstructionResult
from .ranking import cap_hypotheses, rank_hypotheses

DEFAULT_RECONSTRUCT_PROMPT = """You reconstruct LOST text in a fragment.
STRICT RULES:

1. NEVER invent content silently. Produce 2-4 ranked hypotheses ONLY
   where the surviving context constrains the gap.
2. If the context does not constrain the gap, return
   status "no_reconstruction_possible" — a valid and preferred answer.
3. Each hypothesis needs: text, confidence (0-1), evidence (exact
   surviving-context quote). If max confidence < 0.5, return
   "no_reconstruction_possible".

Return ONLY valid JSON:
{"hypotheses": [{"text": "...", "confidence": 0.0, "evidence": "..."}],
 "status": "ok|no_reconstruction_possible"}"""


class FragmentHypothesisEngine:
    """Оркестратор реконструкции: маркеры → LLM-гипотезы → верификация."""

    def __init__(self, llm_client=None, verifier=None, config=None):
        full = config or CONFIG
        self.llm = llm_client or DeepSeekClient()
        self.cfg: FragmentsConfig = full.fragments
        self._verifier = verifier  # ленивое создание, если не передан
        self._logger = get_logger("aeon.fragments")

    # ── публичное API ──

    def reconstruct(self, atom: SemanticAtom, pack=None,
                    verify_hypotheses: Optional[bool] = None) -> ReconstructionResult:
        """Гипотезы восстановления для фрагментарного атома."""
        text = atom.source_text or ""
        markers = self._collect_markers(text, pack)
        base = {
            "markers_count": len(markers),
            "fragment_density": round(len(markers) / max(len(text), 1), 6),
        }

        if not markers:
            return self._no("no_markers", **base)

        gap_like = [m for m in markers if m.kind != "crux"]
        if not gap_like:
            return self._no(
                "cruces_without_external_evidence",
                cruces=[m.text for m in markers if m.kind == "crux"],
                **base,
            )

        if not self.llm.available:
            return self._no("llm_unavailable", **base)

        prompt = self._build_prompt(text, markers, pack)
        result = self.llm._call_json([
            {"role": "system", "content": "You reconstruct fragmentary text. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ], temperature=0.2)

        if result.get("parse_error"):
            return self._no(
                "llm_parse_error",
                raw_preview=str(result.get("raw_response", ""))[:120],
                **base,
            )

        hypotheses = self._parse_hypotheses(result, markers)
        if not hypotheses:
            return self._no("llm_returned_none", **base)

        hypotheses = cap_hypotheses(rank_hypotheses(hypotheses), self.cfg.max_hypotheses)
        max_confidence = max(h.confidence for h in hypotheses)
        if max_confidence < self.cfg.min_confidence:
            return self._no(
                "max_confidence_below_threshold",
                max_confidence=round(max_confidence, 4),
                **base,
            )

        do_verify = self.cfg.verify_hypotheses if verify_hypotheses is None else verify_hypotheses
        if do_verify:
            hypotheses = self._verify_hypotheses(hypotheses, text)
            if not hypotheses:
                return self._no("all_contradicted", **base)

        log_event(self._logger, "reconstruction_done", status="ok",
                  hypotheses=len(hypotheses), markers=len(markers),
                  density=base["fragment_density"])
        return ReconstructionResult("ok", hypotheses=hypotheses, **base)

    # ── внутреннее ──

    @staticmethod
    def _no(reason: str, **base) -> ReconstructionResult:
        return ReconstructionResult(
            "no_reconstruction_possible",
            no_reconstruction=NoReconstruction(reason, base.pop("details", {})),
            **{key: value for key, value in base.items()
               if key in ("markers_count", "fragment_density")},
        )

    def _collect_markers(self, text: str, pack) -> List:
        if pack is not None:
            return pack.detect_markers(text)
        from ..language.base import Marker
        from ..semantic_atom import LACUNA_MARKERS

        markers = []
        for token in LACUNA_MARKERS:
            start = text.find(token)
            while start != -1:
                markers.append(Marker(kind="lacuna", text=token,
                                      start=start, end=start + len(token)))
                start = text.find(token, start + 1)
        markers.sort(key=lambda marker: marker.start)
        return markers

    def _build_prompt(self, text: str, markers: List, pack) -> str:
        base_prompt = None
        if pack is not None:
            base_prompt = pack.prompts.get("reconstruct")
        base_prompt = base_prompt or DEFAULT_RECONSTRUCT_PROMPT
        marker_lines = "\n".join(
            f"- {marker.kind}: {marker.text!r} (offset {marker.start})"
            for marker in markers
        )
        return (
            base_prompt
            + "\n\nFRAGMENT UNDER ANALYSIS:\n" + text
            + "\n\nDETECTED MARKERS:\n" + marker_lines
        )

    def _parse_hypotheses(self, result: dict, markers: List) -> List[Hypothesis]:
        addressed = [marker.text for marker in markers if marker.kind != "crux"]
        hypotheses: List[Hypothesis] = []
        for item in result.get("hypotheses") or []:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            try:
                confidence = float(item.get("confidence", 0.0))
            except (TypeError, ValueError):
                confidence = 0.0
            hypotheses.append(Hypothesis(
                text=text,
                confidence=min(1.0, max(0.0, confidence)),
                evidence=str(item.get("evidence") or "").strip()
                or "обоснование не предоставлено",
                markers_addressed=list(addressed),
            ))
        return hypotheses

    def _get_verifier(self):
        if self._verifier is None:
            from ..verification import VerificationEngine

            self._verifier = VerificationEngine(llm_client=self.llm)
        return self._verifier

    def _verify_hypotheses(self, hypotheses: List[Hypothesis],
                           source_text: str) -> List[Hypothesis]:
        from ..verification import VerificationContext
        from ..verification.verdicts import VERDICT_CONTRADICTED

        verifier = self._get_verifier()
        kept: List[Hypothesis] = []
        for hypothesis in hypotheses:
            verdict = verifier.detective.verify(VerificationContext(
                source_text=source_text, claims=[hypothesis.text],
            ))
            hypothesis.verification = verdict.to_dict()
            hypothesis.verified = verdict.verdict != VERDICT_CONTRADICTED
            if hypothesis.verified:
                kept.append(hypothesis)
        return kept
