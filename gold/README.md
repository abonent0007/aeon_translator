# AEON Gold-standard corpus (шаг 3.3)

Разметка для научной валидации pipeline: метрики качества на **ручных**
аннотациях. **Анти-циркулярность (главный принцип):** gold НЕ создаётся
pipeline'ом AEON; в `gold_mock`-тестах MockLLM возвращает canned-ответы из
ОТДЕЛЬНОЙ фикстуры (`fixtures/mock_responses.json`), сознательно НЕ совпадающие
с gold (проверяется тестом `test_runner_mock_not_circular`).

Статус: разметка готова (28 записей / 6 текстов), `annotator=human:curator` —
**draft до подписи куратора** (стоп №1 пройден: схема одобрена с 3 уточнениями,
внесены в `annotation_schema.json`).

annotations_version: **1.1.1** (Class A source-verified fixes 2026-10-14; см. Change log)

## Change log
### 1.1.1 (2026-10-14) — Class A: source-verified fixes
Обнаружено morph_v1 baseline (модель лингвистически права, gold — нет);
патч по source-diff (без подгонки под model — protocol):
| text | form | было | стало | source-evidence |
|---|---|---|---|---|
| cicero | nocturnum, praesidium, ōra, vultūs | acc | **nom** | параллельные подлежащие при mōvērunt (в gold vigiliae/timor/concursus/locus уже nom — внутренняя несогласованность) |
| homer | ἣ | dat | **nom** | Il. 1.2: субъект ἔθηκε |
| все личные местоимения | ἐγώ/σύ/nōs/tū/ὑμεῖς… | person null | **1/2** | treebank-стандарт (AGDT/PROIEL): личные местоимения несут person (8 форм) |

### 1.1.0 (2026-10-14) — expansion (Phase A/B)

## Schema 1.1.0 — expansion (Phase A/B, 2026-10-14)
Новые поля (optional, mixed 1.0.0/1.1.0 в одном датасете):
- **`annotation_confidence`**: `high|medium|low`; `low`-атомы исключаются из
  метрик (loader, коммит infra); Pindar criterion: ≥50% low → замена на
  Theocritus (факт: **0 low** — Pindar удержан).
- **`expected_morphology`**: `{form, lemma, pos, tense, mood, voice, person,
  case, number, gender}`; не-глаголы: `tense/mood/voice/person = null`;
  причастия: `mood="participle"` + tense/voice + case/number/gender.
- **Правила:** lemma — Attic-standard (grc) / Classical-standard (la),
  form — source-dialect verbatim; элизия — form как в источнике (`δ'`),
  lemma развёрнут (`δέ`); selection — **полное покрытие** nouns/adjectives/
  pronouns/verbs/participles (+articles, `pos="article"`), частицы/наречия/
  предлоги/союзы не размечаются; possessor-генитивы — `role=subject-by-
  convention` + note.
- **Transcription-risk flags:** sophocles s5, rgda s2 (medium); sappho fr.16
  s3/s4 (line-break fragment `ὄτ-`/`τω`, medium); pindar ×3 (Doric, medium).
  **Sappho fr.16 уточнено:** строки 1–4 печатаются БЕЗ supplements в стандартных
  изданиях — `markers=[]` корректно (не упрощение); note исправлен.
- **QID backfill (2026-10-14):** Troy **Q22647**, Olympia **Q38888**,
  Juno **Q125046**, Ajax **Q172725** (найден через «Aias»), Palatium
  **Q200642**. Принцип: Q-ID never from memory — candidate-списки тоже
  верифицируются (5/5 предложенных кандидатов оказались неверны).
- **Forms per atom:** min=2, max=21, median=5.5, IQR=[5.0, 10.75]
  (max=21 — Cicero s4, полное покрытие длинного периода; раздутия нет).
- **Morphology metrics (infra):** per-field (case/number/gender/tense/mood/
  voice/person/pos/lemma); **split by confidence**: `morphology_f1_high` /
  `_medium` / `_all` (тест `test_morphology_f1_splits_by_confidence`);
  denominator = размеченные формы (subset).
  **Denominator semantics (design-choice, accepted 2026-10-14):** denominator
  for per-field F1 = forms where `expected.field ≠ null` AND atom passes
  confidence-filter. Engine returning null or omitting the form → count as
  **miss** for all non-null fields of that form. (Иначе F1 геймится: вернул
  null для сложных — получил 100% на лёгких.)
- **Dual:** homer seg6 (`διαστήτην`, `ἐρίσαντε`, Il. 1.6) — первый dual в gold
  (патч 2026-10-14).
- **Forward-looking enum:** частицы/наречия/союзы/предлоги ENUM'ом в промпте
  morph_v1 предусмотрены, но gold их НЕ содержит (selection rule). Являются
  production-категориями для будущего full-token coverage; в текущих метриках
  не участвуют.
- **Deponent lemma convention (morph_v1):** 1st person singular present
  indicative (`abūtor`, `ἔρχομαι`).
- **Метрики morphology (предстоящий infra-коммит):** per-field (case/number/
  gender/tense/mood/voice/person/pos/lemma), denominator = размеченные формы
  (subset), атомы без поля — N/A.
- **Known limitation:** N≈49 атомов / 220 форм — достаточно для baseline,
  недостаточно для статистических заявлений (Phase-4 trigger: N≥100).

## Покрытие (49 записей / 12 текстов)
| text_id | язык | сегм. | morphology | примечание |
|---|---|---|---|---|
| plato_apologia_17a | grc | 3 | seg1 (retro) | |
| homer_iliad_1 | grc | 7 | seg1–2 (retro) | |
| inscription_ig | grc | 6 | seg1–2 (retro) | |
| papyrus_oxy | grc | 4 | — | |
| sappho_fr31 | grc | 5 | seg1–2 (retro) | |
| sappho_fr16 | grc | 4 | все | Textual medium |
| caesar_bg_1 | la | 3 | — | |
| cicero_cat_1 | la | 4 | все | oratory |
| vergil_aen_1 | la | 3 | все | epic |
| pindar_ol_1 | grc | 3 | все | risk-flagged, 0 low |
| sophocles_ajax_1 | grc | 5 | все | s5 transcription medium |
| rgda_1 | la | 2 | все | epigraphy, s2 medium |

## Состав
- `annotation_schema.json` — схема записи (JSONL: одна строка = атом/сегмент)
- `annotators.json` — реестр аннотаторов (handles; формат `human:<handle>`)
- `texts/<text_id>.txt` — чистые тексты (без заголовков/примечаний)
- `annotations/<text_id>.jsonl` — аннотации
- `fixtures/mock_responses.json` — canned-ответы для gold_mock (отдельно от gold)
- `metrics.md` — целевые метрики + факт-бейзлайн mock

## Уточнения схемы (одобрены куратором, стоп №1)
1. `schema_version: "1.0.0"` — обязательное поле записи (как `aeon_version` в v2);
2. `marker_offsets_relative_to: "segment"` — явный якорь offset'ов (const);
3. `expected_entities[].role` — опционально: `speaker|addressee|subject|object|location|null`
   (заполнен для Plato — addressee, Homer — subject, Caesar — subject/location).

## Методика аннотации
- **Сегментация — эвристика** (документируемая, не догма): verse-level (Homer,
  Sappho), строчная (эпиграфика/папирус), sentence-level (Plato, Caesar).
  **Сегмент ≠ предложение**; расхождения с авто-эвристикой фиксируются в
  `annotator_notes`. Loader проверяет: `segment_text` — уникальная подстрока
  текста; сегменты одного текста НЕ перекрываются (`test_segment_texts_non_overlapping`).
- **Отступы маркеров** — Unicode code points от начала `segment_text` (0-based),
  каждый offset валидируется: `segment[offset:offset+len(text)] == text`.
- **expected_markers** — ВСЕ маркеры сегмента, kind ∈ lacuna/supplement/editorial/
  deletion/uncertain/crux; пустой список — валидная аннотация. Смешанные маркеры
  `[слова ...]` → **решение (A): одна запись `supplement`** — приоритет ЗАКРЫТОГО
  маркера (издатель дополнил утраченное; внутренний пропуск описан текстом
  маркера и note). Альтернативы отклонены: **(B)** lacuna-приоритет теряет факт
  редакторского дополнения; **(C)** два перекрывающихся маркера ломают
  offset-матчинг. Затронуто: inscription L5, papyrus L2/L3.
- **expected_entities** — только ЯВНО упомянутые (не inferred); родовые плюралы
  и местоимения не включаются. `wikidata_id` — только **верифицированные**
  (live Wikidata API, аудит 3.3; напр. Achilles=Q41746, Athenians=Q120096553);
  неверифицированные → `null` (match по тексту, casefold).
- **expected_atom**: `is_fragment` — свойство СЕГМЕНТА (lacuna|supplement → true,
  editorial/deletion/uncertain → false); `completeness_score` — полнота
  ИЗВЛЕЧЕНИЯ (ортогональна is_fragment); ожидание читаемого текста — 1.0.
- **expected_verdicts** — только Plato и Sappho (finding-level); остальные `null`.

## Покрытие (готово: 28 записей; 13 маркеров; 21 сущность)
| text_id | язык | сегм. | markers | entities | verdicts |
|---|---|---|---|---|---|
| plato_apologia_17a | grc | 3 | 0 (чистый текст) | 1 | ✅ |
| homer_iliad_1 | grc | 7 | 0 (чистый текст) | 6 | null |
| inscription_ig | grc | 6 | 6 (lacuna+supplement) | 3 | null |
| papyrus_oxy | grc | 4 | 5 (lacuna+supplement) | 0 | null |
| sappho_fr31 | grc | 5 | 2 (строфные разрывы …) | 0 | ✅ |
| caesar_bg_1 | la | 3 | 0 (чистый текст) | 11 | null |

Примечание: crux-kind в когорте 3.3 отсутствует (нет crux-текстов — CIL-образец
не включён; цель из критериев остаётся на будущее).

## Versioning (стоп №6)
`schema_version` — в каждой записи; `annotations_version` — здесь (1.0.0).
История изменений — git diff. Тесты не хардкодят число сегментов
(читают датасет целиком — `len(dataset.records)`).

## Mock vs Real (стоп №2) и политика baseline (стоп №3)
- `gold_mock` — pipeline с MockLLM (канned-фикстура, фиксирует ТЕКУЩЕЕ
  несовершенное поведение; анти-циркулярность — тест).
- `gold_real` — реальный DeepSeek (нужен ключ; по умолчанию исключён в pytest.ini).
- Два уровня тестов: `*_reports_value` (всегда проходит, печатает метрики) и
  `*_meets_baseline` (ассертит порог; до достижения — `xfail` с явной причиной).
  Провал F1 — сигнал чинить pipeline или пересматривать gold, НЕ повод подгонять
  разметку.

## Прогон
```
python -m aeon.gold.report --dataset gold/annotations/ --mode mock
python -m aeon.gold.report --dataset gold/annotations/ --mode real
pytest -q -m gold_mock -v
pytest -q -m gold_real -v   # skip без ключа
```

## Provenance / лицензия (стоп №4)
- Авторы — public domain; транскрипции — СОБСТВЕННЫЕ AEON (не копии оцифровок
  Perseus/PHI — конвенция проекта, см. examples/LICENSE.md).
- Аннотации — CC0.

## ✅ Аудит RU-флага (стоп-условие 3.3) — ЗАКРЫТ
**Находка:** `examples/greek/plato_apologia_17a.txt` был учебным RU-конспектом
(grc_strict=0, cyr=272), но использовался как grc-вход в demo-прогонах.
**Масштаб:** затронуты 2 файла (оба Plato: `examples/greek/…` и
`examples/plato_sample.txt`); остальные 9 файлов корпуса — подлинные
(grc-тела 87–237 греч. букв / латинские тела), **тесты 2.1 использовали
inline-греческий** (`test_grc_pack.py` — «ἄειδε θεά [...]»), флаг валидацию
паков НЕ затронул.
**Исправление (вариант c):** подлинная grc-транскрипция 17a заменила конспект;
оба RU-файла перенесены в `examples/greek/legacy/` (история сохранена);
regression-защита — `tests/test_examples_corpus.py` (файлы вне legacy/ обязаны
содержать греческие codepoints).
**Исторический дефект:** demo/размерные измерения Plato (до 3.3) выполнялись
на RU-тексте — scientifically meaningless; заменено и зафиксировано.
