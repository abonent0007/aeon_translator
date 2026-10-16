# Phase 3.7 — Export formats: scoping (countersigned 2026-10-16)

Статус: **countersign получен** (решения Q1–Q4, A–H зафиксированы ниже из
сообщения куратора 2026-10-16; сообщения между сессиями терялись — записи
здесь = источник правды). Стоп-точки: №2 TEI-mapping (до кода TEI),
№3 Plato-пример (до финала).

## Scope

**Вход:** только `.aeon v2` (predictions; reader-валидация ДО экспорта).
Пакет `aeon/export/`, CLI `python -m aeon.export --aeon PATH --format
tei|bib|md|jsonld [--out DIR/]`. stdlib-only, offline, детерминизм.

## Решения (countersigned)

| # | Решение |
|---|---|
| Q1 | **BibTeX split:** `aeon_artifact.bib` + `editions.bib`; `--bib-split off` для single-file |
| Q2 | `--out DIR/`; `index.md` при N>1 |
| Q3 | Position-in-source → **inline**; иначе **standoff** |
| Q4 | Пакет `aeon/export/` + `python -m aeon.export` ✓ |
| A | **Determinism:** triple-hash (content/atom/status?) + TZ/LANG-независимость + запрет `now()/random/uuid4` (AST-guard) |
| B | **Legacy-contract warning** в TEI/MD/BibTeX (если v2 несёт legacy-поля) |
| C | JSON-LD: **inline `@context`** |
| D | TEI: **namespace + полный teiHeader + minidom** (well-formedness тест) |
| E | MD: collection DIR + index |
| F | Resilient к пустым optional (absent slot → no-op, не ошибка) |
| G | **Predictions only** + `test_export_rejects_gold_jsonl` (gold-разметка отклоняется) |
| H | Закрыт: morphology **уже в v2** (`schemas/aeon_v2.json` slot; additive не нужен) |

## H2 finding (новое, из probe 2026-10-16)

**Markers НЕ персистятся в v2:** ни `atom.*`, ни `traces.*` (TRACE_SLOTS =
extraction/null, entity_linking/null, verification/null, reconstruction,
variant_readings, morphology, cross_references; `traces.extraction` = null в
живом файле — extractor-результаты спроецированы в атом; маркеры не пишутся
нигде — 0 hits в `aeon/format/writer.py|reader.py`, `aeon/translator.py`).

**Следствие для TEI:** маркерные элементы (`<gap/> <supplied> <del> <add>
<unclear> <sic>`) **не могут быть сгенерированы из v2** — предложение:
N/A + backlog `v2_markers_persistence` (additive `atom.markers` или
`traces.extraction.markers`), решение — за куратором. Альтернатива: additive
сейчас (расширяет v2-формат; по прецеденту H — только при явной необходимости).

## TEI-mapping (стоп №2, draft — до кода TEI)

| v2 элемент | TEI | Условие |
|---|---|---|
| `source.content` | `<text xml:lang="{lang}"><body><p>` (+ `<lb/>` по строкам) | всегда |
| `atom.entities[]` (span+qid) | inline `<name type="{type}" ref="{Q…/Pleiades}">{span}</name>` | span найден в content (первое вхождение) |
| entity без вхождения span | standoff `<standOff><listAnnotation><annotation>` | fallback (Q3/F) |
| `traces.morphology[]` (form/lemma) | inline `<w lemma="{lemma}" ana="#pos-{pos}">` | форма найдена; иначе standoff |
| `traces.cross_references[]` | standoff `<linkGrp type="crossReferences"><link target="#seg…">` (локусы) | при наличии |
| `traces.variant_readings` | `<app>/<rdg source="#{edition}">` inline по locus (line) | если строка найдена; иначе `<listWit>`+standoff |
| `traces.reconstruction` | standoff `<note type="reconstruction">` (гипотезы/вердикт) | при наличии |
| `traces.verification` (verdicts) | standoff `<note type="verification">` | при наличии |
| маркеры | **N/A** (H2) | — |
| `<teiHeader>` | fileDesc (title = text_id; author = **нет в v2** → omit + note) + encodingDesc (pipeline steps) + profileDesc (lang) + note: provenance `{aeon_version, generator, atom_hash, created_at, thresholds_snapshot}` | всегда (D) |

**Segment-локусы:** без offset-схемы v2 → `#seg{N}`-якоря по порядковому
вхождению сегмента в content (детерминизм A).

## Backlog (новое)

- `v2_markers_persistence` (H2; additive; решение куратора).
- `tag_tei_markers` — после persistence.
- (ранее) `crossref_chronology_aware_harness`, `crossref_source_work_disambiguation`.
