# AEON 3.4 — Cross-references: scoping plan (Plan Mode, 2026-10-14; rev.2)

Статус: **rev.2 на апрув** (учтены issues 1–6 countersign). Build не начинается до апрува.

## 0. Framing (Issue 1): PILOT

3.4 — **pilot**: engine end-to-end + preliminary F1. Ожидаемые ~4 связи → granularity 0.25;
**никаких quality-claims** из n=4. Формулировка отчёта 3.4.3: «F1 = X на n=4 — preliminary,
statistically meaningful measurement deferred to F4 (target N≥20 пар)».

## 1. Taxonomy (Issue 2: 3 kind'а, разделены)

| Kind | Операционный критерий | Scope |
|---|---|---|
| `direct_citation` | named-маркер («ut ait X», название работы) ИЛИ verbatim-run ≥5 знаменательных лемм подряд | ✅ (gold ×0, prompt-only) |
| `adaptation` | scholarly consensus (ссылка на издание/комментарий в notes) + ≥3 **параллельных** лемм; **включает переводы** (Livius Odusia) — с явной пометкой `annotator_notes: "translation (… ← …)"` | ✅ |
| `formulaic_echo` | **гибридное evidence**: формульный маркер (proem: invocation-verb + subject-of-song) **И/ИЛИ** ≥1 лемма-пара; в записи обязателен `matched_formula` (строка-описание формулы) ЛИБО непустые `matched_lemmas` | ✅ |
| structural_parallel | без лексического/формульного якоря | ❌ 3.4.1 |
| thematic_allusion / lexical_borrowing | субъективно / Ф4 | ❌ |

В пилоте: adaptation ×2 (Catull.51←Sapph.31; Livius←Od.1), formulaic_echo ×2 (Vergil↔Il.1;
Vergil↔Od.1), **direct_citation ×0** (в корпусе нет named-цитат — kind поддержан промптом
(few-shot вне gold), не упражняется в gold; задокументированная limitation).

## 2. Gold format — annotations 1.2.0 (additive; rev.3 — fixes countersign)

```json
"expected_cross_references": [
  {"source": {"text_id": "sappho_fr31", "segment_id": 1},
   "target": {"text_id": "catullus_51", "segment_id": 1},
   "kind": "adaptation",
   "matched_lemma_pairs": [
     {"source_lemma": "ἐκεῖνος", "target_lemma": "ille"},
     {"source_lemma": "ἴσος", "target_lemma": "pār"},
     {"source_lemma": "θεός", "target_lemma": "deus"},
     {"source_lemma": "φαίνομαι", "target_lemma": "videō"}],
   "matched_formula": null,
   "confidence": "high",
   "annotator_notes": "Adaptation of Sapph. 31 (consensus; cf. commentaries). Chronology: source=Sappho."}
]
```
- **`direction` — УДАЛЕНО** (blocking #2): семантика «citing» была двусмысленной. Конвенция
  фиксирована: **`source` = хронологически более ранний текст; `target` = поздний**
  (schema README). Цитационный смысл — только в `annotator_notes` («X adapts/cites Y»).
  Метрика неориентированная — порядок на F1 не влияет.
- **`matched_lemma_pairs` — структура** (blocking/Issue 3): dict-пары
  `{source_lemma, target_lemma}` вместо строки «X/Y»; леммы — **канонические**
  (как в gold `expected_morphology`, не поверхностные формы).
- **Инвариант (loader, шаг 3.4.1; design principle #9):** ∀пары:
  `source_lemma ∈ lemmas(source.segment)` И `target_lemma ∈ lemmas(target.segment)`
  (сегменты с morphology; при отсутствии — skip, документировано); тесты
  `test_cross_ref_pairs_within_segments`, `test_cross_ref_lemma_pairs_well_formed`.
- **Recency-требования:** `direct_citation` — ≥5 пар ПОДРЯД (verbatim-run) или named-маркер;
  `formulaic_echo` — ≥1 пара ИЛИ `matched_formula ≠ null`; `adaptation` — pairs optional
  (consensus/издание в notes).
- **`confidence` = уверенность в СУЩЕСТВОВАНИИ связи** (не в kind); `low` → excluded.
- **`offset` — НЕ включаем** (additive позже).
- **Indeclinables convention (Issue 5):** несклоняемые — `case` по **синтаксической функции**
  (`fās` (субъект) = nominative; `nihil`×6 (субъекты при mōvērunt) = nominative),
  `number=singular`, `gender=neuter`; поверхностная форма неизменна. Фикс существующих
  `nihil`-записей (case null → nominative) — входит в 1.2.0 change-log.
- **`matched_lemma_pairs` — только канонические POS-совместимые пары** (обе леммы из
  morphology соответствующих сегментов, invariant #9). Поверхностные/функциональные
  параллели (наречия, cross-POS, семантически-неточные пары) → **в `annotator_notes`**
  («further parallels … documented in scholarship»). Пример: `ἐνάντιος/adversus` (adverb,
  не аннотируется) и `ὑπακούω/audiō` (неточная эквивалентность) — в notes.
- **`matched_formula` формат (determined):** dict
  `{"label": "<открытый-малый-набор>", "description": "<свободное описание>"}`.
  Стартовые label: `proem_invocation` (иные — по мере появления). String отклонён
  (немáшино-проверяем); validator: label и description — непустые строки
  (тест `test_cross_ref_matched_formula_format`).
- **Confidence для echo:** формула-без-лексем или 1 лемма-пара → **medium**
  (existence вероятна, но evidence слабее lemma-anchored); ≥2 пары + формула → high.
- **Non-annotated listing (рекомендация):** для сегментов, где >2 токенов исключены
  по selection rule, `annotator_notes` содержит явный список
  («Non-annotated (per selection rule): sī (conj), adversus (adv), identidem (adv), et (conj)»).
- `offset` — НЕ включаем (additive позже);
- **Recency/структура:** см. §2 rev.3 (direction удалён; `matched_lemma_pairs` структура;
  канонические леммы; инвариант #9); тесты: `test_cross_ref_direct_citation_requires_lemmas`,
  `test_cross_ref_adaptation_lemmas_optional`, `test_cross_ref_echo_requires_lemmas_or_formula`,
  `test_cross_ref_pairs_within_segments`;

## 3. Метрика

F1 по **неориентированной паре (source_seg, target_seg, kind)**, split by kind, symmetric +
confidence-splits (high/all; medium при наличии). Инверсия source↔target матчится. `low` excluded.

## 4. Detectable set

Текущий gold: ~1 (vergil↔homer). Расширение (+3 текста, ~7 атомов):
`catullus_51` (la), `odyssey_1` (grc, Od. 1.1–5), `livius_odusia_1` (la, fr.1).
Итог: **~4 связи** (см. §0 framing). Fallback pre-committed: <3 verifiable на sample → defer 3.4 → 3.7.

## 5. Approach + engine input (Issue 5)

**Brute-force v1**: все текстовые пары C(15,2)=105 (лемма-префильтр отклонён **эмпирически**:
мусор через артикли + структурно слеп для cross-language); cap $0.10; optimization — Ф4 (корпус>30).
**Engine input = pair-based** (a): `detect(text_a_segments, lang_a, text_b_segments, lang_b) →
list[cross_ref]` для этой пары; 1 вызов на пару; тест `test_crossref_engine_pair_format`.
Output: локусы (text_id/segment_id) + kind + matched_lemmas + confidence + evidence.

## 6. Circularity / anti-leak

Annotation human; engine `aeon/crossrefs/` не импортирует/не читает `gold/` (AST-скан);
few-shot вне gold.

## 7. FP-процесс (Issue 4) — часть шага 3.4.3

1. Engine-прогон → FPs собраны **отдельным списком**;
2. Annotator проверяет **по источнику** (не по output): реальна ли связь?
3. Реальна → gold patch 1.2.1 c source-diff («было/стало/почему»; protocol Class A);
4. Нереальна → реальный FP, остаётся в F1.
(N=4 pilot: ожидаемые пары уже в gold; FP-процесс — на случай неожиданных находок.)

## 8. Шаги и стоп-точки (обновлено)

| # | Шаг | Стоп-точка |
|---|---|---|
| 3.4.0 | Gold 1.2.0: schema-additions (+3 текста, ~7 атомов, ~4 связи), тесты схемы | **sample 2 cross-ref (Catull.51↔Sapph31, Livius↔Od1) до массовой** |
| 3.4.1 | Infra: loader mixed 1.0.0/1.1.x/1.2.0 + low-exclusion; metrics pair-F1×kind×confidence-splits; ≥6 тестов | — |
| 3.4.2 | Engine `aeon/crossrefs/` (pair-based, contract v1: 3 kinds, loci, lemma-anchors, null-semantics) | **prompt v1 до кода** |
| 3.4.3 | Measure real (105 пар, ≤$0.10) + FP-процесс §7 + preliminary-отчёт | **отчёт до правок** |

## 9. Out-of-scope / fallback

Out: structural (3.4.1), thematic, lexical (Ф4), multi-hop (Ф4), offset, prefilter (Ф4), kind-confidence (backlog).
Fallback: <3 verifiable на sample → defer 3.4 → 3.7 (export formats).

## 10. Coverage gaps (explicit — design principle #8)

| Gap | Статус | Impact | Trigger / путь |
|---|---|---|---|
| **`direct_citation`: 0 gold-примеров** | acknowledged (MEDIUM) — prompt-only | F1_direct = **N/A**; kind не валидируется пайплайном (few-shot понимание LLM не проверено) | новый корпус со схолиастом/комментатором ИЛИ внешний запрос на direct_citation |
| `offset` локалей не включён | deferred (additive) | точность локалей = сегмент | потребность passage-level точности |
| kind-confidence (уверенность в ТИПЕ) | backlog | kinds могут перепутываться без штрафа | при усложнении kinds/росте N |
| multi-hop chains | backlog/Ф4 | цепочки A→B→C не детектируются | Ф4 |
