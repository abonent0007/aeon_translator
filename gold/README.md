# AEON Gold-standard corpus (шаг 3.3)

Разметка для научной валидации pipeline: метрики качества на **ручных**
аннотациях. **Анти-циркулярность (главный принцип):** gold НЕ создаётся
pipeline'ом AEON; в `gold_mock`-тестах MockLLM возвращает canned-ответы из
ОТДЕЛЬНОЙ фикстуры (`fixtures/mock_responses.json`), сознательно НЕ совпадающие
с gold (проверяется тестом `test_runner_mock_not_circular`).

Статус: разметка готова (28 записей / 6 текстов), `annotator=human:curator` —
**draft до подписи куратора** (стоп №1 пройден: схема одобрена с 3 уточнениями,
внесены в `annotation_schema.json`).

annotations_version: **1.0.0**

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
