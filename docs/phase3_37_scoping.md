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

## H2 finding (probe + code-verified 2026-10-16) — severity **MEDIUM**

**Markers НЕ персистятся в v2** — подтверждено 4/4:
1. `detect_markers()` вызывается: `aeon/language/base.py:66` (`is_fragment()`),
   `aeon/fragments/engine.py:147`, extractor — `detect_lacunae`
   (`aeon/extractor.py:206`);
2. результат используется для `is_fragment` (`aeon/extractor.py:206,232`,
   `language/base.py:66`) — да;
3. в v2 не сохраняется — 0 «marker»-hits в `format/writer.py|reader.py`,
   `translator.py`; live-probe: TRACE_SLOTS без markers, `atom.markers` нет;
4. **loss**: v2 знает *что* фрагмент есть (bool), но не *какие* маркеры и *где*.

```
finding_v2_markers_not_persisted:
  severity: MEDIUM
  impact: export cannot produce TEI <gap/>, <supplied/>;
          forensic reproducibility of marker detection lost
  scope: not blocking 3.7
  trigger: TEI-export demand OR need to re-audit marker detection
  fix: additive v2 (atom.markers: list[Marker]) — separate commit after 3.7
```

**Решение: N/A в 3.7** (export не расширяет source-format); additive — отдельным
коммитом после 3.7 (решение куратора).

## TEI-mapping (стоп №2, draft — до кода TEI)

| v2 элемент | TEI | Условие |
|---|---|---|
| `source.content` | `<text xml:lang="{lang}"><body><p>` (+ `<lb/>` по строкам) | всегда |
| `atom.entities[]` (span+qid) | inline `<name type="{type}" ref="{Q…/Pleiades}">{span}</name>` | span найден в content (первое вхождение) |
| entity без вхождения span | standoff `<standOff><listAnnotation><annotation>` | fallback (Q3/F) |
| `traces.morphology[]` (form/lemma) | **conditional inline** `<w lemma="{lemma}" ana="#pos-{pos}">` — **только если form встречается в content РОВНО ОДИН РАЗ**; иначе standoff `<listAnnotation>` (refinement 1: 2+ вхождений = ambiguous offset) | при наличии |
| `traces.cross_references[]` | standoff `<linkGrp type="crossReferences"><link target="#seg…">` (локусы) | при наличии |
| `traces.variant_readings` | **standoff always** (refinement 2): `<listWit>` (editions) + `<listAnnotation>` (loci/readings/выбранное); inline `<app>/<rdg>` отложен до v2 locus→offset (additive, Ф4) | при наличии |
| `traces.reconstruction` | standoff `<note type="reconstruction">` (гипотезы/вердикт) | при наличии |
| `traces.verification` (verdicts) | standoff `<note type="verification">` | при наличии |
| маркеры | **N/A** — v2 не персистит (H2, MEDIUM; backlog `v2_markers_persistence`) | — |
| `<teiHeader>` | fileDesc (title = text_id; author = **нет в v2** → omit + note) + encodingDesc (pipeline steps) + profileDesc (lang) + note: provenance `{aeon_version, generator, atom_hash, created_at, thresholds_snapshot}` | всегда (D) |

**Segment-локусы:** без offset-схемы v2 → `#seg{N}`-якоря по порядковому
вхождению сегмента в content (детерминизм A).

## Backlog (новое)

- `v2_markers_persistence` (H2; additive; решение куратора).
- `tag_tei_markers` — после persistence.
- (ранее) `crossref_chronology_aware_harness`, `crossref_source_work_disambiguation`.
