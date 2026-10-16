"""Prompts + few-shot crossrefs engine (шаг 3.4.2).

Frozen prompt v1.2 (2026-10-16): + D5 translation-exception (SAME RELATIVE
ORDER, explicit OVERRIDE) + D6 same-author. Ранее: proem-приоритет (D2),
cross-author (D1), canonical-grounding (D4). Few-shot — structured данные
(FEW_SHOTS): рендерятся в промпт через render_examples(), тест-инвариант
`test_few_shot_not_in_gold_or_scoring` проверяет вне-corpus/вне-scoring.

Константы ЗЕРКАЛЯТ aeon.gold.loader (CROSS_REF_KINDS / CONFIDENCE_LEVELS /
FORMULA_LABELS) — синхронность стережёт тест (пакет не импортирует gold).
"""

import json
from typing import Any, Dict, List

CROSS_REF_KINDS = frozenset({"direct_citation", "adaptation", "formulaic_echo"})
CONFIDENCE_LEVELS = frozenset({"high", "medium", "low"})
FORMULA_LABELS = frozenset({"proem_invocation"})
PROMPT_VERSION = "1.2"

# Few-shot (rev.3): 2 positive + 1 hard negative + 1 direct_citation.
# Все тексты ВНЕ gold-корпуса (15) и вне scoring-пар (105) — конвенция
# countersign 2026-10-15. P2/P4 используют Aratus 1 в разных ролях
# (formula-source / cited-author) — kinds суть свойства СВЯЗИ, не источника.
FEW_SHOTS: List[Dict[str, Any]] = [
    {
        "header": "adaptation, medium: consensus + 2 secure lexical anchors; both texts OUTSIDE the evaluation corpus",
        "a": {"text_id": "alcaeus_338", "lang": "grc", "segments": [
            "ὔει μὲν ὁ Ζεύς, ἐκ δ' ὀράνω μέγας χείμων, πεπάγαισιν δ' ὑδάτων ῥόαι "
            "[...] κάββαλλε τὸν χείμων', ἐπὶ μὲν τίθεις πῦρ, ἐν δὲ κέρναις οἶνον "
            "ἀφειδέως μέλιχρον"]},
        "b": {"text_id": "horace_carm_1_9", "lang": "la", "segments": [
            "vidēs ut altā stet nive candidum Sōracte, nec iam sustineant onus "
            "silvae labōrantēs, gelūque flūmina cōnstitērunt acūtō? dissolve frīgus, "
            "ligna super focō large repōnēns atque benignius dēprōme quadrimum "
            "Sabīnā, ō Thaliarche, merum diōtā."]},
        "output": {"cross_references": [{
            "source": {"text_id": "alcaeus_338", "segment_id": 1},
            "target": {"text_id": "horace_carm_1_9", "segment_id": 1},
            "kind": "adaptation",
            "matched_lemma_pairs": [
                {"source_lemma": "ῥοή", "target_lemma": "flūmen"},
                {"source_lemma": "οἶνος", "target_lemma": "merum"}],
            "matched_formula": None,
            "confidence": "medium",
            "reasoning": "Hor. Carm. 1.9 reworks the storm-and-remedy scene of "
                         "Alc. 338 (scholarly consensus); two secure lexical "
                         "anchors — the rest is scene-level correspondence."}]},
    },
    {
        "header": "formulaic_echo, high: shared formula + 2 pairs; OUTSIDE corpus",
        "a": {"text_id": "aratus_phaen", "lang": "grc", "segments": [
            "ἐκ Διὸς ἀρχώμεσθα, τὸν οὐδέποτ' ἄνδρες ἐῶμεν ἄρρητον."]},
        "b": {"text_id": "theocritus_17", "lang": "grc", "segments": [
            "ἐκ Διὸς ἀρχώμεσθα καὶ ἐς Δία λήγετε, Μοῖσαι,"]},
        "output": {"cross_references": [{
            "source": {"text_id": "aratus_phaen", "segment_id": 1},
            "target": {"text_id": "theocritus_17", "segment_id": 1},
            "kind": "formulaic_echo",
            "matched_lemma_pairs": [
                {"source_lemma": "Ζεύς", "target_lemma": "Ζεύς"},
                {"source_lemma": "ἄρχω", "target_lemma": "ἄρχω"}],
            "matched_formula": {"label": "proem_invocation",
                                "description": "proem opening formula 'ἐκ Διὸς "
                                               "ἀρχώμεσθα' (begin from Zeus), "
                                               "verbatim shared"},
            "confidence": "high",
            "reasoning": "Theocritus 17 opens with the verbatim Aratean proem "
                         "formula."}]},
    },
    {
        "header": "negative, HARD: same genre and subject matter, no dependence; OUTSIDE corpus",
        "a": {"text_id": "livy_auc_1", "lang": "la", "segments": [
            "Iam prīmum omnium satis constat Trōiā captā in cēterōs saevītum "
            "esse Trōiānōs, duōbus, Aenēae Antēnōrīque ... omne iūs bellī "
            "Achīvōs abstinuisse."]},
        "b": {"text_id": "tacitus_ann_1", "lang": "la", "segments": [
            "Urbem Rōmam ā principiō rēgēs habuēre; lībertātem et cōnsulātum "
            "L. Brūtus īnstitūit."]},
        "output": {"cross_references": []},
    },
    {
        "header": "direct_citation, high: explicit citation formula naming the author; OUTSIDE corpus",
        "a": {"text_id": "aratus_phaen", "lang": "grc", "segments": [
            "ἐκ Διὸς ἀρχώμεσθα, τὸν οὐδέποτ' ἄνδρες ἐῶμεν ἄρρητον."]},
        "b": {"text_id": "ap_xii_1", "lang": "grc", "segments": [
            "ἐκ Διὸς ἀρχώμεσθα, καθὼς εἴρηκεν Ἄρατος: ὑμῖν δ', ὦ Μοῦσαι, "
            "σήμερον οὐκ ἐνοχλῶ."]},
        "output": {"cross_references": [{
            "source": {"text_id": "aratus_phaen", "segment_id": 1},
            "target": {"text_id": "ap_xii_1", "segment_id": 1},
            "kind": "direct_citation",
            "matched_lemma_pairs": [],
            "matched_formula": None,
            "confidence": "high",
            "reasoning": "AP XII.1 (Straton) explicitly names Aratus ('as "
                         "Aratus said'), citing his Phaenomena opening."}]},
    },
]

_PROMPT = """You compare two ancient-text passages and detect CROSS-REFERENCES between them — textual dependence (citation, adaptation, or formulaic echo). Return ONLY valid JSON.

TEXT_A (earlier, source) — id: "{text_a_id}", language: {lang_a}:
{a_segments}

TEXT_B (later, target) — id: "{text_b_id}", language: {lang_b}:
{b_segments}

CONTRACT RULES:
1. A cross-reference is TEXTUAL DEPENDENCE, not similarity: themes may coincide without a link. If no dependence exists — return an empty list. Cross-references hold between works of DIFFERENT authors: shared diction or formulas within one author's own corpus (e.g., two poems by the same poet, or two genres by the same prose author) are NOT cross-references — do not report them (this includes two works by the SAME author — e.g., the Iliad and the Odyssey are both "Homer"; do not report such intra-author parallels even if you would call them "intra-epic formulaic echoes").
2. Kinds:
   - "direct_citation": an explicit named marker in the text (author or work, e.g. "as Aratus said") OR a verbatim run of >= 5 content lemmas.
   - "adaptation": scholarly-recognized reworking or translation ("scholarly recognized" = the dependence is discussed in standard commentaries/editions; judge from your knowledge; uncertain -> omit or confidence "low"); 3+ parallel content lemmas raise confidence (see scale).
   - "formulaic_echo": a shared formula. "matched_formula" is REQUIRED. The formula label set is CLOSED: ["proem_invocation"] — the opening of a poem invoking a Muse/god to sing or beginning "from a god" (e.g. "ἐκ Διὸς ἀρχώμεσθα"). If a shared formula does NOT fit this label, do NOT return it as formulaic_echo — you may still report adaptation/direct_citation if their criteria hold independently. An opening-formula link has PRIORITY: if the shared element is the proem opening (invocation/singing verb + Muse, or "begin from a god"), return formulaic_echo — do NOT downgrade it to adaptation just because lexical pairs are also present. EXCEPTION to that priority: if the target is a close translation of the source proem (>= 3 source-lemmas whose canonical forms appear in the target in the SAME RELATIVE ORDER — not necessarily adjacent, e.g. virum ~ ἄνδρα, mihi ~ μοι, īnsece ~ ἔννεπε), OVERRIDE the kind to adaptation — a translation is adaptation, not echo.
   If several kinds could describe the same link, choose the ONE with the strongest evidence — specificity beats pair count: a proem-opening link is formulaic_echo even when 3+ pairs exist. Return a single entry per link — never the same link under multiple kinds.
3. Every returned reference MUST contain:
   "source": {"text_id": "{text_a_id}", "segment_id": N}   (MUST equal TEXT_A)
   "target": {"text_id": "{text_b_id}", "segment_id": M}   (MUST equal TEXT_B)
   "kind": one of ["direct_citation", "adaptation", "formulaic_echo"]
   "matched_lemma_pairs": [{"source_lemma": "...", "target_lemma": "..."}]
   "matched_formula": {"label": <one of the closed set>, "description": "..."} or null (non-null IF AND ONLY IF kind == "formulaic_echo")
   "confidence": "high" | "medium" | "low"
   "reasoning": optional one sentence (recommended, especially for adaptation/echo)
   "segment_id" = the index shown in the input (A1->1, A2->2; B1->1, B2->2).
4. Lemma discipline: canonical lemmas in the SOURCE language (never translate); POS-compatible pairs only (noun<->noun, verb<->verb); no adverbs/particles/conjunctions. A pair must be a SECURE equivalent; loose/accidental parallels do NOT belong in "matched_lemma_pairs" — mention them in "reasoning" instead. Use canonical dictionary forms (ἀείδω — not the inflected ἄειδε) that actually occur in their own text in some inflected form; a lemma absent from its text is an invention — drop the pair. If both a citation formula and a verbatim run are present for the same link, keep ONE direct_citation entry: include the verbatim pairs in "matched_lemma_pairs" and note the citation formula in "reasoning".
5. Negative case: if you are not confident that a textual dependence exists — omit it (or use confidence "low"). Do not pad the output.
6. No hallucination: mention a named author/work ONLY if it is explicitly present in the given texts.

CONFIDENCE SCALES (existence of the link):
  direct_citation: high = verbatim >= 5 content lemmas OR an explicit citation formula naming an author/work (e.g. "as Aratus said"); medium = an author/work named without citation syntax; low = weak/indirect.
  adaptation:      high = consensus + >= 3 secure pairs; medium = consensus with 1-2 secure pairs; low = weak.
  formulaic_echo:  high = formula + >= 2 pairs; medium = formula + 1 pair; low = formula only.

OUTPUT (JSON only):
{{"cross_references": [{{"source": {{...}}, "target": {{...}}, "kind": "...",
  "matched_lemma_pairs": [...], "matched_formula": null, "confidence": "...",
  "reasoning": "..."}}]}}

{examples}

Now compare TEXT_A and TEXT_B and return ONLY the JSON object.
"""


def _number_segments(segments: List[str], prefix: str) -> str:
    return "\n".join(f"{prefix}{index}. {segment}"
                     for index, segment in enumerate(segments, 1))


def render_examples() -> str:
    """Рендер few-shot блока из structured FEW_SHOTS (единый источник правды)."""
    blocks: List[str] = []
    for index, shot in enumerate(FEW_SHOTS, 1):
        a, b = shot["a"], shot["b"]
        lines = [f"--- Example {index} ({shot['header']}) ---",
                 f"TEXT_A ({a['lang']}):"]
        lines += [f"A{i}. {seg}" for i, seg in enumerate(a["segments"], 1)]
        lines.append(f"TEXT_B ({b['lang']}):")
        lines += [f"B{i}. {seg}" for i, seg in enumerate(b["segments"], 1)]
        lines.append(json.dumps(shot["output"], ensure_ascii=False))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def build_prompt(text_a: Dict[str, Any], lang_a: str,
                 text_b: Dict[str, Any], lang_b: str) -> str:
    """Собрать полный промпт для пары (text: {text_id, segments})."""
    return (_PROMPT
            .replace("{text_a_id}", str(text_a["text_id"]))
            .replace("{lang_a}", str(lang_a))
            .replace("{a_segments}",
                     _number_segments(list(text_a.get("segments") or []), "A"))
            .replace("{text_b_id}", str(text_b["text_id"]))
            .replace("{lang_b}", str(lang_b))
            .replace("{b_segments}",
                     _number_segments(list(text_b.get("segments") or []), "B"))
            .replace("{examples}", render_examples()))
