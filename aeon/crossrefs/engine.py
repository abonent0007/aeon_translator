"""crossrefs engine (шаг 3.4.2): pair-based детекция кросс-ссылок.

`CrossReferenceEngine.detect(text_a, lang_a, text_b, lang_b)` — один LLM-вызов
на пару (temperature 0.0); ответ валидируется теми же правилами, что gold
loader (kind/confidence enum, echo→formula+label-enum, shape пар), невалидные
записи дропаются с событием `crossref_validation_drop` (не роняют пару).

Post-filter (countersign refinement 1, 3.4.2): grounded-пары — source_lemma
обязана присутствовать в TEXT_A, target_lemma — в TEXT_B (норм-префикс >= 3;
len<=2 не допускается); ungrounded пары дропаются, adaptation без grounded-пар
дропается целиком (echo/direct_citation переживают — formula/marker несут
свидетельство).
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from ..llm_client import DeepSeekClient
from ..logging_config import get_logger, log_event
from .prompts import (CONFIDENCE_LEVELS, CROSS_REF_KINDS, FORMULA_LABELS,
                      build_prompt)

_LOGGER = get_logger("aeon.crossrefs")

_TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def _norm(value: Any) -> str:
    """NFD → strip combining → casefold (греческий/латынь-friendly)."""
    decomposed = unicodedata.normalize("NFD", str(value))
    stripped = "".join(ch for ch in decomposed
                       if not unicodedata.combining(ch))
    return stripped.casefold()


def _grounded(lemma: Any, segments: List[str]) -> bool:
    """Grounding леммы в исходном тексте (refinement 1):
    len<=2 — не допускается; len>=3 — вхождение или общий префикс >= 3.
    """
    lemma_norm = _norm(lemma)
    if len(lemma_norm) < 3:
        return False
    for segment in segments:
        for token in _TOKEN_RE.findall(str(segment)):
            token_norm = _norm(token)
            if not token_norm:
                continue
            if lemma_norm in token_norm:
                return True
            shared = 0
            for lemma_char, token_char in zip(lemma_norm, token_norm):
                if lemma_char != token_char:
                    break
                shared += 1
            if shared >= 3:
                return True
    return False


def _ground_ref(ref: Dict[str, Any], a_segments: List[str],
                b_segments: List[str]
                ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], bool]:
    """Фильтр пар по grounding. → (ref', ungrounded_pairs, dropped_ref)."""
    pairs = list(ref.get("matched_lemma_pairs") or [])
    kept_pairs: List[Dict[str, Any]] = []
    ungrounded: List[Dict[str, Any]] = []
    for pair in pairs:
        if (_grounded(pair.get("source_lemma"), a_segments)
                and _grounded(pair.get("target_lemma"), b_segments)):
            kept_pairs.append(pair)
        else:
            ungrounded.append(pair)
    grounded_ref = (ref if len(kept_pairs) == len(pairs)
                    else {**ref, "matched_lemma_pairs": kept_pairs})
    ref_dropped = ref["kind"] == "adaptation" and not kept_pairs
    return grounded_ref, ungrounded, ref_dropped


def _check_ref(ref: Any, text_a_id: str, text_b_id: str,
               a_count: int, b_count: int) -> Tuple[bool, str]:
    """Зеркало правил gold loader для одной записи. → (ok, reason)."""
    if not isinstance(ref, dict):
        return False, "entry_not_object"
    for key in ("source", "target", "kind", "confidence"):
        if key not in ref:
            return False, f"missing_{key}"
    if ref["kind"] not in CROSS_REF_KINDS:
        return False, f"kind_out_of_enum:{ref['kind']}"
    if ref["confidence"] not in CONFIDENCE_LEVELS:
        return False, f"confidence_out_of_enum:{ref['confidence']}"
    for locus, expected_id, count in (("source", text_a_id, a_count),
                                      ("target", text_b_id, b_count)):
        value = ref[locus]
        if not isinstance(value, dict):
            return False, f"{locus}_not_object"
        if value.get("text_id") != expected_id:
            return False, f"{locus}_text_id_mismatch:{value.get('text_id')}"
        segment_id = value.get("segment_id")
        if not isinstance(segment_id, int) or not (1 <= segment_id <= count):
            return False, f"{locus}_segment_id_out_of_range:{segment_id}"
    if (ref["source"]["text_id"], ref["source"]["segment_id"]) == \
            (ref["target"]["text_id"], ref["target"]["segment_id"]):
        return False, "self_reference"
    if ref["kind"] == "formulaic_echo":
        formula = ref.get("matched_formula")
        if (not isinstance(formula, dict)
                or not str(formula.get("label") or "").strip()
                or not str(formula.get("description") or "").strip()):
            return False, "echo_missing_matched_formula"
        if formula["label"] not in FORMULA_LABELS:
            return False, f"formula_label_out_of_enum:{formula['label']}"
    for pair in (ref.get("matched_lemma_pairs") or []):
        if (not isinstance(pair, dict)
                or not str(pair.get("source_lemma") or "").strip()
                or not str(pair.get("target_lemma") or "").strip()):
            return False, "bad_lemma_pair_shape"
    return True, ""


class CrossReferenceEngine:
    """Детекция cross-references для текстовой пары (A=ранний, B=поздний)."""

    def __init__(self, llm_client: Optional[DeepSeekClient] = None,
                 trace_id: Optional[str] = None):
        self.llm = llm_client or DeepSeekClient()
        self.trace_id = trace_id

    def detect(self, text_a: Dict[str, Any], lang_a: str,
               text_b: Dict[str, Any], lang_b: str) -> List[Dict[str, Any]]:
        """→ validated список cross-ref записей (возможно пустой)."""
        a_segments = [str(seg) for seg in (text_a.get("segments") or [])]
        b_segments = [str(seg) for seg in (text_b.get("segments") or [])]
        if not a_segments or not b_segments:
            log_event(_LOGGER, "crossref_invalid_input",
                      text_a=str(text_a.get("text_id")),
                      text_b=str(text_b.get("text_id")),
                      trace_id=self.trace_id)
            return []
        if not self.llm.available:
            log_event(_LOGGER, "crossref_llm_unavailable",
                      trace_id=self.trace_id)
            return []

        prompt = build_prompt(text_a, lang_a, text_b, lang_b)
        data = self.llm._call_json([
            {"role": "system",
             "content": "You are a cross-reference detector for ancient "
                        "texts. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ], temperature=0.0, max_tokens=2000)

        if data.get("parse_error") or "cross_references" not in data:
            log_event(_LOGGER, "crossref_parse_error",
                      reason=str(data.get("parse_error") or "no cross_references key"),
                      raw_preview=str(data.get("raw_response", ""))[:120],
                      trace_id=self.trace_id)
            return []
        refs = data.get("cross_references")
        if not isinstance(refs, list):
            log_event(_LOGGER, "crossref_invalid_output",
                      got=type(refs).__name__, trace_id=self.trace_id)
            return []

        kept: List[Dict[str, Any]] = []
        dropped = 0
        pairs_dropped = 0
        for ref in refs:
            ok, reason = _check_ref(ref, str(text_a["text_id"]),
                                    str(text_b["text_id"]),
                                    len(a_segments), len(b_segments))
            if not ok:
                dropped += 1
                log_event(_LOGGER, "crossref_validation_drop", reason=reason,
                          trace_id=self.trace_id)
                continue
            grounded_ref, ungrounded, ref_dropped = _ground_ref(
                ref, a_segments, b_segments)
            for pair in ungrounded:
                pairs_dropped += 1
                log_event(_LOGGER, "crossref_pair_ungrounded", pair=pair,
                          text_a=str(text_a["text_id"]),
                          text_b=str(text_b["text_id"]),
                          trace_id=self.trace_id)
            if ref_dropped:
                dropped += 1
                log_event(_LOGGER, "crossref_ref_dropped",
                          reason="adaptation_without_grounded_pairs",
                          text_a=str(text_a["text_id"]),
                          text_b=str(text_b["text_id"]),
                          trace_id=self.trace_id)
                continue
            kept.append(grounded_ref)
        log_event(_LOGGER, "crossref_done",
                  text_a=str(text_a["text_id"]), text_b=str(text_b["text_id"]),
                  kept=len(kept), dropped=dropped, pairs_dropped=pairs_dropped,
                  trace_id=self.trace_id)
        return kept
