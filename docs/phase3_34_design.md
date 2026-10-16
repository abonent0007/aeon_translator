# AEON 3.4 — Cross-references: scoping plan (Plan Mode, 2026-10-14)

Статус: **DRAFT на апрув**. Build не начинается до апрува taxonomy и шага 3.4.0.

## 1. Taxonomy (scope)

| Kind | Операционное определение | В scope |
|---|---|---|
| `direct_citation` | (a) явный named-цитатный маркер («как сказал X», название работы) ИЛИ (b) near-verbatim совпадение ≥3 знаменательных лемм; сюда же **adaptation** при scholarly consensus (Catull. 51 ← Sappho 31; Livius Odusia ← Od. 1) | ✅ |
| `formulaic_echo` | общая формула ≥2 знаменательных лемм в жанрово-родственном контексте (epic invocation, proem-формулы) | ✅ |
| structural_parallel | тематическая параллель без лексического якоря | ❌ (3.4.1 backlog) |
| thematic_allusion | субъективная аллюзия | ❌ |
| lexical_borrowing | грецизмы в латыни | ❌ (Ф4: morphology) |

Правила аннотации: только **verifiable** (lemma-anchored) связи; спорные — `confidence: medium`, `low`-записи исключаются из метрик.

## 2. Gold format — annotations 1.2.0 (additive)

```json
"expected_cross_references": [
  {"direction": "citing", 
   "source": {"text_id": "vergil_aen_1", "segment_id": 1},
   "target": {"text_id": "homer_iliad_1", "segment_id": 1},
   "kind": "formulaic_echo",
   "matched_lemmas": ["canō", "ἀείδω", "vir/ἀνήρ", "arma/μῆνις"],
   "confidence": "high",
   "annotator_notes": "proem-invocation; arma virumque ← μῆνιν ... Ἀχιλῆος"}
]
```
Решения: **offset — НЕ включаем** в v1 (границы сегмента достаточны; offset — additive позже);
`matched_lemmas` — **обязательны** (ядро verifiability; для adaptation допустимо название работы строкой в notes при леммах ≥3);
`confidence` — уверенность АННОТАТОРА в факте связи (high/medium; low → исключение из метрик); `direction` — справочный (метрика неориентированная); `segment_id` — обязателен; cross-ref может указывать на сегмент вне данного текста.

## 3. Метрика

**F1 по неориентированной паре (source_segment, target_segment, kind)** — как рекомендовано; symmetric
(FP и FN равнозначны); split by kind (`direct_citation`, `formulaic_echo`). Дополнительно: recall
per kind + precision per kind (формулируется в отчёте, дериватив от tp/fp/fn). Инверсия source↔target
матчится (неориентированная пара); `confidence: low` записи в denominator не входят.

## 4. Detectable set — честная оценка

**Текущий gold (49 атомов, 12 текстов): ~1–2 связи** (vergil_aen_1 ↔ homer_iliad_1, formulaic_echo;
возможно pindar ↔ homer — но это lexical, out of scope). **Для baseline недостаточно.**

**Расширение (+3 текста, ~7 атомов):**
| text_id | пара | kind | памятник |
|---|---|---|---|
| `catullus_51` (la, ~3 атома) | ↔ sappho_fr31 | direct_citation (adaptation, consensus) | Catull. 51 = латинская адаптация Sapph. 31 |
| `odyssey_1` (grc, ~3 атома, Il. Od. 1.1–5) | ↔ vergil_aen_1 | formulaic_echo (proem-invocation) | «ἄνδρα μοι ἔννεπε» ← «arma virumque canō» |
| `livius_odusia_1` (la, 1 атом) | ↔ odyssey_1 | direct_citation (translation) | Livius Andronicus Odusia fr.1: «Virum mihi, Camena, insece versutum» |

Ожидаемые detectable cross-refs после расширения: **~4** (vergil↔homer, catullus↔sappho, odyssey↔vergil,
livius↔odyssey). N=4 — **baseline-минимум** (известное ограничение, Ф4: ≥20 при расширении корпуса).

## 5. Approach — brute-force v1 (неорёшенный выбор документирован)

Пробный лемма-фильтр **отклонён**: даёт мусор через артикли И не работает для cross-language пар
(главные пары — la↔grc). C(15,2)=105 текстовых пар × 1 LLM-вызов (оба текста в промпте, ответ — список
связей с локалями) ≈ **$0.05** (cache-hit префиксов снижает). Бюджет-cap $0.10. Фильтр-оптимизация —
Ф4 (триггер: корпус >30 текстов). Cost-cap по стоп-условию: >$0.10 → стоп.

## 6. Circularity / anti-leak

Annotation — human (curator countersign); detection engine `aeon/crossrefs/` **не импортирует и не читает
`gold/`** (anti-leak тест: AST/import-скан + отсутствие чтения gold-путей в engine); prompt не содержит
gold-примеров из нашего корпуса (few-shot — вне gold, как во всех контрактах).

## 7. Шаги, критерии, стоп-точки

| # | Шаг | Критерии | Стоп-точка |
|---|---|---|---|
| 3.4.0 | **Gold 1.2.0**: schema-additions + +3 текста (7 атомов) + разметка связей (4) + countersign samples | schema additive; loader принимает 1.0.0/1.1.0/1.1.1/1.2.0; ≥3 verifiable связи | **СТОП: sample-аннотации (catullus_51↔sappho31, livius↔odyssey1) до массовой** |
| 3.4.1 | **Infra**: loader (поле+валидация+excluded low), metrics (cross-ref F1 pair×kind), тесты (≥6) | F1=0.00 с denominators при отсутствии предсказаний (как morph) | — |
| 3.4.2 | **Engine `aeon/crossrefs/`** (contract-цикл): prompt v1 (kinds, loci, lemma-anchors, null-semantics), prefilter=None (brute 105), run в gold-runner | prompt countersigned до кода; completeness-verify по парам; anti-leak тест | **СТОП: prompt v1 до кодирования** |
| 3.4.3 | **Measure (real)**: полный прогон детекции, report F1 pair×kind + cost/latency | ≤$0.10; failures=0; F1 отчёт с gold-diff | **СТОП: отчёт измерений** до любых правок |

## 8. Out-of-scope (backlog)

structural_parallel (3.4.1), thematic_allusion, lexical_borrowing (Ф4), multi-hop chains (Ф4),
фильтр-оптимизация (Ф4, триггер корпус>30), offset-точность локалей (additive позже).

## 9. Fallback

Если при countersign sample окажется <3 verifiable связей — **defer 3.4 → 3.7 (export formats)**
(per кураторскую рекомендацию; не привязываться к номеру).
