# Phase 3.7 — Export formats: final report (шаг 3.7)

Дата: 2026-10-16. Статус: **impl завершён; стоп №3 закрыт** (Plato/Sappho артефакты).
Дизайн: `docs/phase3_37_scoping.md` (countersigned Q1–Q4 + A–H + refinements 1–2 + H2).

## Scope

Экспорт `.aeon v2` (predictions only) в исследовательские форматы: **TEI-XML**,
**Markdown**, **JSON-LD**, **BibTeX** (artifact + editions). stdlib-only, offline,
детерминизм. Пакет `aeon/export/`, CLI `python -m aeon.export`.

## Deliverables

| Элемент | Файл |
|---|---|
| Пакет | `aeon/export/` (common, markdown, tei, jsonld, bibtex, demo, `__main__`) |
| CLI | `python -m aeon.export --aeon PATH [PATH…] --format {tei,md,jsonld,bib} [--out DIR] [--label NAME] [--bib-split {on,off}]` |
| Тесты | `tests/test_export.py` — **17** (gold-reject, well-formedness, refinements, legacy-триггеры, детерминизм, AST-guard, CLI) |
| Suite | **476 passed** |
| Примеры | `gold/real_runs/2026-10-16_export_demo/` — Plato (mock) + Sappho (real) + `export/` |

## Ключевые решения (реализованы)

- **Q1** BibTeX split: `{name}.aeon_artifact.bib` + `{name}.editions.bib`
  (`--bib-split off` → один файл); editions — из apparatus (`Voigt (1971)`),
  нет apparatus → honest «none found».
- **Q2/E** `--out DIR/` + `index.md` при N>1.
- **Q3 + refinement 1** inline где позиция однозначна: entities (span найден);
  morphology — **только уникальные формы** (`test_morphology_inline_only_when_unique`),
  неоднозначные → standoff; иначе честный `<listAnnotation>`.
- **refinement 2** variant_readings — **standoff always** (`<listWit>` +
  apparatus-annotations); inline `<app>` — после v2 locus→offset (Ф4).
- **A** детерминизм: triple-hash (content/atom/meaning) в provenance;
  TZ/LANG-независимость (`test_export_env_independent`); запрет
  `now/random/uuid` — **AST-guard** (`test_export_no_impure_calls`).
- **B** legacy-warning (триггеры, финал): `extensions.legacy_v1_original` **ИЛИ**
  `metadata.extractor_contract != "v1"` (native v2 от 2.7.x, напр. `v3.0-legacy`);
  `meaning_hash` — штатное v2-поле → НЕ триггерит (эмпирика Plato) —
  `test_export_warns_on_v30_legacy_contract` / `test_export_no_warning_on_v1_contract`.
- **C** JSON-LD inline `@context`; entity `@type` schema.org-mapping; `sameAs`
  Wikidata/Pleiades/Trismegistos.
- **D** TEI namespace + полный teiHeader (fileDesc/encodingDesc/pipeline/
  profileDesc/revisionDesc) + minidom well-formedness; `author` в v2 нет → omit+note.
- **F** resilience: пустые optional-слоты → no-op (не ошибка).
- **G** predictions only: gold JSONL (single- и multi-line) → `ExportError`.

## Демонстрации

- **Plato (mock):** standoff-fallback для RU-mock-spans (`span_not_in_text`) —
  поведение корректно, указано как mock-артефакт.
- **Sappho (real, `--real`):** **inline-entities подтверждены** —
  `<persName type="person">Σαπφώ</persName>`, `<persName>Voigt</persName>`;
  standoff пуст. Mock-span caveat закрыт.

## Known limitations / coverage

- **Markers — N/A** (H2, severity MEDIUM в state): v2 не персистит маркеры →
  TEI `<gap/>/<supplied>` невозможны до additive `atom.markers`
  (отдельный коммит после 3.7; trigger: TEI-export demand / marker re-audit).
- `text_id`/`author` отсутствуют в v2 → label из CLI/stem + omit-note.
- Segment-якоря `#seg1` (v2 = один атом).
- Variant-readings renderer — generic (финализация структуры при интеграции
  selector → v2 trace).
- RIS — не в scope (countersign: BibTeX-only).

## Design principles

#22 (export-before-UI, candidate→active by 3.7) · **#23 (executable guards,
ACTIVE: 3 применения)**.

## Next

**Phase 3 Consolidation** (retro + principles #1–#23 consolidated + public
summary) → решение Ф4-vs-3.6.
