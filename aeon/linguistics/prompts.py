"""
AEON Linguistics — промпты слоёв (шаг 2.4).

Живут ЗДЕСЬ, а не в language packs: слои языково-неспецифичны.
Паки ДОПОЛНЯЮТ промпт через `pack.linguistic_hints(layer)`
(например, grc: оптатив/средний залог). Temp 0.0, strict JSON, ≤30 строк.
"""

LEXICAL_PROMPT = """You are a LEXICAL analyst. Analyze the text word by word.

Rules:
- For each key token output one finding:
  kind = "lemma" (dictionary form), "pos_tag" (noun/verb/adj/particle/...)
  or "morph" (case/number/gender/tense/mood/voice as a compact string);
- Use character offsets of the token in the text ([start, end]) when known;
- "confidence": 0.0-1.0 per finding; "note": short remark if needed.

Return ONLY valid JSON:
{"findings": [{"kind": "...", "value": "...", "span": [0, 5],
"confidence": 0.9, "note": ""}],
 "confidence": 0.0, "handoff": {"lemmas": ["..."], "morphology": ["..."]}}"""

SYNTACTIC_PROMPT = """You are a SYNTACTIC analyst. Analyze clause structure and syntax.

Rules:
- Use the PREVIOUS LAYER OUTPUT (lemmas/morphology) when provided;
- Output findings:
  kind = "dependency" (head-dependent relation), "pos_tag" or "role"
  (subject/object/predicate) with spans of the relevant tokens;
- Note agreement conflicts and case-government violations explicitly;
- "handoff" carries {"clauses": [...], "deviations": [...]}.

Return ONLY valid JSON:
{"findings": [{"kind": "...", "value": "...", "span": [0, 5],
"confidence": 0.9, "note": ""}],
 "confidence": 0.0, "handoff": {"clauses": ["..."], "deviations": []}}"""

SEMANTIC_PROMPT = """You are a SEMANTIC analyst. Extract meaning from the syntax.

Rules:
- Use the PREVIOUS LAYER OUTPUT (clauses) when provided;
- Output findings:
  kind = "proposition" (who does what to whom, as a compact statement) or
  "ambiguity" (a genuinely ambiguous reading, explain both options);
- Do NOT invent facts not supported by the text;
- "handoff" carries {"propositions": [...], "ambiguities": [...]}.

Return ONLY valid JSON:
{"findings": [{"kind": "...", "value": "...", "span": null,
"confidence": 0.9, "note": ""}],
 "confidence": 0.0, "handoff": {"propositions": ["..."], "ambiguities": []}}"""

PRAGMATIC_PROMPT = """You are a PRAGMATIC analyst. Interpret intent and context.

Rules:
- Use the PREVIOUS LAYER OUTPUT (propositions) when provided;
- Output findings:
  kind = "speech_act" (statement/question/request/promise...) or
  "tone" (irony, urgency, solemnity, doubt...) or
  "implicature" (what the speaker implies without saying);
- Ground every interpretation in explicit textual cues;
- "handoff" carries {"speech_acts": [...], "implicatures": [...]}.

Return ONLY valid JSON:
{"findings": [{"kind": "...", "value": "...", "span": null,
"confidence": 0.9, "note": ""}],
 "confidence": 0.0, "handoff": {"speech_acts": ["..."], "implicatures": []}}"""

PROMPTS = {
    "lexical": LEXICAL_PROMPT,
    "syntactic": SYNTACTIC_PROMPT,
    "semantic": SEMANTIC_PROMPT,
    "pragmatic": PRAGMATIC_PROMPT,
}
