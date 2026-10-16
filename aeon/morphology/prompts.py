"""morph_v1 — промпт морфологического анализа (шаг 3.2, contract v1).

Плейсхолдеры: {text}, {language}, {forms_numbered}.
Контракт: все входные формы обязаны присутствовать в выходе (index 1-based,
последовательно, без пропусков); null = «не применимо ИЛИ не восстановимо».
См. docs-цикл 3.2 и gold/README.md (enum-сверка с gold, design-choices).
"""

MORPH_V1_PROMPT = '''You perform morphological analysis of an ancient-language text. Return ONLY valid JSON (no markdown).

TEXT: "{text}"
LANGUAGE: {language}
FORMS (analyze EVERY form; numbered):
{forms_numbered}

CONTRACT RULES:
1. Output MUST contain an entry for EVERY input form, in order, "index" 1-based,
   sequential, no gaps. If uncertain about a field — null for THAT field; NEVER drop an entry.
2. lemma = Attic-standard (grc) / Classical-standard (la); form = source-dialect verbatim.
   Deponent lemma convention: use 1st person singular present indicative
   (la: abūtor, sequor; grc: ἔρχομαι).
3. null semantics: NOT APPLICABLE (verb has no case) OR UNRECOVERABLE (broken fragment). Never guess.
4. Dialects (Doric/Aeolic/Homeric) -> keep source form, map to the standard lemma.
5. Elision: form as in source (δ', τιν'), lemma expanded (δέ, τις).
   Attic contraction: form as printed (φιλῶ), lemma uncontracted (φιλέω).
6. Line-break fragments (ὄτ-, -ται): form verbatim; unrecoverable fields = null.
7. Language enforcement: form/lemma in the SOURCE language — never translate.
8. ALLOWED VALUES (use exactly these strings):
   pos:    noun | verb | adjective | participle | pronoun | article | numeral | adverb |
           conjunction | preposition | particle | interjection
   tense:  present | imperfect | aorist | future | perfect | pluperfect | future_perfect
   mood:   indicative | imperative | subjunctive | optative | infinitive | participle
           (grc optative is common in Pindar, Sappho, tragedy — never collapse into subjunctive)
   voice:  active | middle | passive | mediopassive | deponent (la)
   person: 1 | 2 | 3
   case:   nominative | genitive | dative | accusative | vocative | ablative (la)
   number: singular | dual | plural
   gender: masculine | feminine | neuter | common (epicene, e.g. κύων)
9. Non-verbs: tense/mood/voice/person = null. Participles: mood="participle", person=null;
   tense/voice/case/number/gender filled. Infinitives: mood="infinitive", person/number=null.
   Articles: pos="article", case/number/gender filled.

Return JSON:
{{"forms": [{{"index": 1, "form": "...", "lemma": "...", "pos": "...", "tense": null,
 "mood": null, "voice": null, "person": null, "case": null, "number": null, "gender": null}}, ...]}}

--- Example 1 (Greek; Iliad 2.1-2 — NOT from corpus) ---
TEXT: "ἄλλοι μέν ῥα θεοί τε καὶ ἀνέρες ἱπποκορυσταί εὗδον παννύχιοι, Δία δ᾽ οὐκ ἔχε νήδυμος ὕπνος"
FORMS: 1. ἄλλοι 2. θεοί 3. ἀνέρες 4. ἱπποκορυσταί 5. εὗδον 6. Δία 7. ἔχε 8. νήδυμος 9. ὕπνος
{{"forms": [
 {{"index": 1, "form": "ἄλλοι", "lemma": "ἄλλος", "pos": "adjective", "tense": null, "mood": null, "voice": null, "person": null, "case": "nominative", "number": "plural", "gender": "masculine"}},
 {{"index": 2, "form": "θεοί", "lemma": "θεός", "pos": "noun", "tense": null, "mood": null, "voice": null, "person": null, "case": "nominative", "number": "plural", "gender": "masculine"}},
 {{"index": 3, "form": "ἀνέρες", "lemma": "ἀνήρ", "pos": "noun", "tense": null, "mood": null, "voice": null, "person": null, "case": "nominative", "number": "plural", "gender": "masculine"}},
 {{"index": 4, "form": "ἱπποκορυσταί", "lemma": "ἱπποκορυστής", "pos": "noun", "tense": null, "mood": null, "voice": null, "person": null, "case": "nominative", "number": "plural", "gender": "masculine"}},
 {{"index": 5, "form": "εὗδον", "lemma": "εὕδω", "pos": "verb", "tense": "imperfect", "mood": "indicative", "voice": "active", "person": 3, "case": null, "number": "plural", "gender": null}},
 {{"index": 6, "form": "Δία", "lemma": "Ζεύς", "pos": "noun", "tense": null, "mood": null, "voice": null, "person": null, "case": "accusative", "number": "singular", "gender": "masculine"}},
 {{"index": 7, "form": "ἔχε", "lemma": "ἔχω", "pos": "verb", "tense": "imperfect", "mood": "indicative", "voice": "active", "person": 3, "case": null, "number": "singular", "gender": null}},
 {{"index": 8, "form": "νήδυμος", "lemma": "νήδυμος", "pos": "adjective", "tense": null, "mood": null, "voice": null, "person": null, "case": "nominative", "number": "singular", "gender": "masculine"}},
 {{"index": 9, "form": "ὕπνος", "lemma": "ὕπνος", "pos": "noun", "tense": null, "mood": null, "voice": null, "person": null, "case": "nominative", "number": "singular", "gender": "masculine"}}]}}

--- Example 2 (Greek with article; Odyssey 1.10 — NOT from corpus) ---
TEXT: "τῶν ἁμόθεν γε, θεά, θύγατερ Διός, εἰπὲ καὶ ἡμῖν"
FORMS: 1. τῶν 2. θεά 3. θύγατερ 4. Διός 5. εἰπὲ 6. ἡμῖν
{{"forms": [
 {{"index": 1, "form": "τῶν", "lemma": "ὁ", "pos": "article", "tense": null, "mood": null, "voice": null, "person": null, "case": "genitive", "number": "plural", "gender": "masculine"}},
 {{"index": 2, "form": "θεά", "lemma": "θεά", "pos": "noun", "tense": null, "mood": null, "voice": null, "person": null, "case": "vocative", "number": "singular", "gender": "feminine"}},
 {{"index": 3, "form": "θύγατερ", "lemma": "θυγάτηρ", "pos": "noun", "tense": null, "mood": null, "voice": null, "person": null, "case": "vocative", "number": "singular", "gender": "feminine"}},
 {{"index": 4, "form": "Διός", "lemma": "Ζεύς", "pos": "noun", "tense": null, "mood": null, "voice": null, "person": null, "case": "genitive", "number": "singular", "gender": "masculine"}},
 {{"index": 5, "form": "εἰπὲ", "lemma": "λέγω", "pos": "verb", "tense": "aorist", "mood": "imperative", "voice": "active", "person": 2, "case": null, "number": "singular", "gender": null}},
 {{"index": 6, "form": "ἡμῖν", "lemma": "ἐγώ", "pos": "pronoun", "tense": null, "mood": null, "voice": null, "person": null, "case": "dative", "number": "plural", "gender": null}}]}}

--- Example 3 (Latin; CONSTRUCTED — not an attestation) ---
TEXT: "Rōma ā Rōmulō condita est."
FORMS: 1. Rōma 2. Rōmulō 3. condita 4. est
{{"forms": [
 {{"index": 1, "form": "Rōma", "lemma": "Rōma", "pos": "noun", "tense": null, "mood": null, "voice": null, "person": null, "case": "nominative", "number": "singular", "gender": "feminine"}},
 {{"index": 2, "form": "Rōmulō", "lemma": "Rōmulus", "pos": "noun", "tense": null, "mood": null, "voice": null, "person": null, "case": "ablative", "number": "singular", "gender": "masculine"}},
 {{"index": 3, "form": "condita", "lemma": "condō", "pos": "participle", "tense": "perfect", "mood": "participle", "voice": "passive", "person": null, "case": "nominative", "number": "singular", "gender": "feminine"}},
 {{"index": 4, "form": "est", "lemma": "sum", "pos": "verb", "tense": "present", "mood": "indicative", "voice": "active", "person": 3, "case": null, "number": "singular", "gender": null}}]}}

Now analyze FORMS in order and return ONLY the JSON object.'''

MORPH_FIELDS = ("form", "lemma", "pos", "tense", "mood", "voice", "person",
                "case", "number", "gender")
