# Phase 3.4 — Cross-references pilot: final report (шаг 3.4.3)

Дата: 2026-10-16. Статус: **pilot закрыт — `v1.2.1` pilot-final** (countersign куратора).

## Scope

Pair-based детекция кросс-ссылок между 15 текстами gold-корпуса (105 пар):
`direct_citation` / `adaptation` / `formulaic_echo`. Границы kind'ов — pilot
research question (N=4 связи), решён переопределением headline-метрики.

## Deliverables

- **`aeon/crossrefs/`**: `prompts.py` (frozen prompt v1.2.1 + structured
  FEW_SHOTS ×5 + render), `engine.py` (pair-based `detect`; пост-фильтры:
  schema-валидация → grounded-pairs → same-author), `demo.py` (CLI:
  `--a/--b/--all-pairs`, `--authors`, overwrite-guard `--force`).
- **`tools/crossrefs_f1.py`**: kind-level + **HEADLINE link-level F1**.
- **gold 1.2.1**: 54 записи / 15 текстов (+`author_id`; 4 cross-refs, 11
  lemma-пар; invariant #9; fail-fast loader).
- **Тесты**: 27 crossrefs (9 infra + 18 engine); **suite 459 green**.
- Run-артефакты: `gold/real_runs/2026-10-16_xref_pilot{,_v11,_v12,_v121}/`.

## Версии промпта (история kind-границы)

| version | изменение | livius×od | Vergil×2 | kind all-macro |
|---|---|---|---|---|
| v1.0 | базовая | adaptation ✓ | adaptation ✗ | — |
| v1.1 | D1 cross-author + D2/D3 proem-priority + D4 canonical + post-filter | echo ✗ | echo ✓ | 0.583 |
| v1.2 | D5 translation-exception (relative-order) | adaptation ✓ | adaptation ✗ (overfire) | 0.250 |
| **v1.2.1** | **D7 онтологический: version-of-source + no-hallucinated-evidence + Example 5** | ✓ (правильное направление) | echo ✓ | **0.619** |

## Метрики (pilot-final; 105 пар, $0.037, ~147 s, prompt_version=1.2.1)

**HEADLINE — link-level F1 (kind-agnostic):** all **0.800** (tp=4, fp=2),
high 0.667. Recall **4/4 во всех версиях** (детекция стабильна).

**Diagnostic kind-macro:** all 0.619 (adaptation f1 0.67 tp1 fn1; echo f1 0.57
tp2 fp3). medium-bucket: fn1 — bucket-drift `il×vergil` (gold medium vs engine
high; §10).

| metric | v1.1 | v1.2 | **v1.2.1** |
|---|---|---|---|
| link all-F1 | 0.727 | 0.800 | **0.800** |
| link high-F1 | 0.600 | 0.667 | **0.667** |
| kind all-macro | 0.583 | 0.250 | **0.619** |
| FP (link) | 3 | 2 | **2** |

## FP-процесс (§7) — закрыт для pilot

| FP | класс | вердикт |
|---|---|---|
| #3 `homer_il→livius` | wrong-source attribution (Odusia = перевод **Odyssey**) | **accepted known FP** (N=1; промптом не чинится — work-knowledge; Ф4 `crossref_source_work_disambiguation`) |
| #7 `livius→vergil` | possible genuine allusion | **FP retained** — source-проба не нашла consensus-level свидетельств (учебные juxtapositions лишь); candidate для Ф4 scholarly-review |

Gold-patch'ей по итогам §7: **0** (обе связи — не «неучтённое золото»).

## Anti-leak / инварианты

Few-shot вне corpus-15 и scoring-пар (тест `test_few_shot_not_in_gold_or_scoring`;
Example 5 — LXX→Vulgata + Aratus→Theocritus, не scoring); AST-скан пакета
(no-gold-import); invariant #9; same-author drop (`author_id`, нет «anonymous»
sentinel); engine-валидация ответов (drop + события `crossref_validation_drop` /
`crossref_pair_ungrounded` / `crossref_same_author_drop`).

## Coverage gaps / known limitations (полные — `docs/phase3_34_design.md` §10)

- `direct_citation` ×0 в gold (prompt-only; Example 4 — формат-защита).
- `confidence: low` — механика self-abstention работает (Cat×Sapph16, Od×Pindar —
  обе excluded из метрик).
- Bucket-drift `il×vergil` (gold medium pre-scale-extension vs engine high).
- Direction-sensitivity harness (алфавитный порядок пар, без chronology;
  **не влияет на headline**, влияет на kind-diagnostic).
- Post-filter: suppletive-стемы и `ῥοή`-коллизия (метрически нейтральны —
  пары не входят в F1-ключ).

## Бюджет

Per-run: **$0.037** (105 вызовов; 243K in / 2.6K out; ~1.4 s/call).
Всего pilot ≈ **$0.20** (4 полных прогона + raw-проверки; включая $0.037
от двойного исполнения — инфра-fix: overwrite-guard, #18).

## Design principles (рождены/активированы в 3.4)

#9 schema-инварианты программно · #10 validators-before-write · #11 absence≠0 ·
#12 few-shot-typical · #13 fix-rule-not-example · #14 confidence-scale=evidence ·
#15 committed-state+CI · #16 kind-priority=contextual · #17 ground-truth filter ·
#18 infra-idempotent · #19 explicit-exceptions · #20 whack-a-mole=wrong-framing ·
#21 verify-trigger-not-artifact.

## Backlog (Ф3/Ф4)

- `crossref_chronology_aware_harness` — хронологический порядок пар (trigger:
  corpus >30).
- `crossref_source_work_disambiguation` (Ф4; #3-класс wrong-source).
- gold bucket-drift revision (Ф4); contract v1.1 (Ф4).
- 3.6 Web UI/API — очередь после решения по следующему шагу.
