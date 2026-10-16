"""
morph_v1 — engine морфологического анализа (шаг 3.2, contract v1).

Публичный API: `MorphEngine(llm_client=...)` → `analyze(text, language, forms)`
→ список словарей `{form, lemma, pos, tense, mood, voice, person, case,
number, gender}`, выровненный по входным формам (1:1, тот же порядок).

Engine-side verify (Minor 1, 3.2): сортировка по index; проверка
`len(output) == len(input)` и `output[i].form == input[i]`; нарушение →
событие `morph_engine_completeness_violation` (HIGH) + all-null fallback
для отсутствующих/несовпавших форм (denominator защищён gold'ом).
"""

from typing import Any, Dict, List, Optional

from ..llm_client import DeepSeekClient
from ..logging_config import get_logger, log_event
from .prompts import MORPH_FIELDS, MORPH_V1_PROMPT

_LOGGER = get_logger("aeon.morphology")


def _null_entry(form: str) -> Dict[str, Any]:
    entry: Dict[str, Any] = {"form": form}
    for field in MORPH_FIELDS[1:]:
        entry[field] = None
    return entry


class MorphEngine:
    """LLM-морфология: per-atom batch (text + формы) → разбор каждой формы."""

    def __init__(self, llm_client: Optional[DeepSeekClient] = None,
                 trace_id: Optional[str] = None):
        self.llm = llm_client or DeepSeekClient()
        self.trace_id = trace_id

    def analyze(self, text: str, language: str,
                forms: List[str]) -> List[Dict[str, Any]]:
        forms = [str(form).strip() for form in (forms or [])]
        if not forms:
            return []
        if not self.llm.available:
            log_event(_LOGGER, "morph_llm_unavailable", trace_id=self.trace_id)
            return [_null_entry(form) for form in forms]

        numbered = "\n".join(f"{index}. {form}"
                             for index, form in enumerate(forms, 1))
        prompt = (MORPH_V1_PROMPT
                  .replace("{text}", text)
                  .replace("{language}", language)
                  .replace("{forms_numbered}", numbered))
        # Бюджет вывода: ~250 токенов/форму (JSON с 11 полями), пол 2000, потолок 8000.
        # Прогон 2026-10-14 (morph_t2): атом на 25 форм обрезал max_tokens=2000 →
        # parse_error → null-cascade; найдено полным прогоном (engine budget bug).
        max_tokens = max(2000, min(8000, len(forms) * 250))
        data = self.llm._call_json([
            {"role": "system",
             "content": "You are a morphological analyzer. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ], temperature=0.0, max_tokens=max_tokens)

        if data.get("parse_error") or not isinstance(data.get("forms"), list):
            log_event(_LOGGER, "morph_parse_error",
                      reason=str(data.get("parse_error") or "no forms list"),
                      raw_preview=str(data.get("raw_response", ""))[:120],
                      trace_id=self.trace_id)
            return [_null_entry(form) for form in forms]

        items = [item for item in data["forms"] if isinstance(item, dict)]

        def _index_of(item: Dict[str, Any]) -> int:
            value = item.get("index")
            return value if isinstance(value, int) else 10 ** 6  # нечисловые — в конец

        items.sort(key=_index_of)

        violation = len(items) != len(forms) or any(
            str(item.get("form") or "").strip() != forms[i]
            for i, item in enumerate(items))
        if violation:
            log_event(_LOGGER, "morph_engine_completeness_violation",
                      expected=len(forms), got=len(items),
                      trace_id=self.trace_id)

        result: List[Dict[str, Any]] = []
        for index, form in enumerate(forms):
            item = items[index] if index < len(items) else None
            if item is None or str(item.get("form") or "").strip() != form:
                result.append(_null_entry(form))
                continue
            entry = {"form": form}
            for field in MORPH_FIELDS[1:]:
                entry[field] = item.get(field)
            result.append(entry)
        log_event(_LOGGER, "morph_done", forms=len(forms),
                  violation=violation, trace_id=self.trace_id)
        return result


def morph_engine(text: str, language: str, forms: List[str],
                 llm_client: Optional[DeepSeekClient] = None
                 ) -> List[Dict[str, Any]]:
    """Convenience-обёртка (используется как hook в gold/runner)."""
    return MorphEngine(llm_client=llm_client).analyze(text, language, forms)
