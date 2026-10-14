"""
AEON Variant Readings — промпт селектора (шаг 3.5).

Стоп-точки: «Do NOT generate new text»; editions СКРЫТЫ (без «престижа
издания»); rule 3 — измеримо (fewer editorial marks) + честный fallback -1;
note про контекст (locus в контекст НЕ входит, эхо-совпадения не аргумент).
≤30 строк, temp 0.0, strict JSON.
"""

SELECT_READING_PROMPT = """You select ONE reading for a single textual locus.
You MUST NOT invent text.

LOCUS CONTEXT (surviving text around the locus):
"{CONTEXT}"

CANDIDATE READINGS (choose exactly one index):
{READINGS_NUMBERED}

Rules:
1. Choose ONLY from the given readings. Do NOT generate new text.
2. Base the choice on grammatical and contextual compatibility — NOT on any
   assumptions about editions or their prestige.
3. If two or more readings are equally compatible:
   a. prefer the one with FEWER editorial marks ([...], †...†, <...>) —
      less editorial intervention is generally safer;
   b. if still tied, return chosen_index: -1, confidence: 0.0 and let the
      caller decide (no false certainty).
4. If the context is insufficient to decide, return chosen_index: -1,
   confidence: 0.0.
5. reasoning: one short sentence grounded in specific words of the context.

Note: the context does NOT include the locus itself. Do not treat partial
string overlap with the context as evidence of correctness.

Return ONLY valid JSON:
{"chosen_index": 0, "confidence": 0.0, "reasoning": "..."}"""
