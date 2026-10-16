# Phase 3 — Midpoint Checkpoint (2026-10-14)

Сводка перед scoping 3.4. **Никакого кода** — только состояние, принципы,
backlog-триггеры и решения по остатку Ф3.

## 1. Сделано

| Шаг | Артефакты | Ключевые коммиты |
|---|---|---|
| **3.1 `.aeon v2`** | `aeon/format/` (writer/reader/validator/versioning), `schemas/aeon_v2.json`, D1–D4, mock-guard, v1-миграция (frozen fixture) | `e8cf5ca`…`50ea764` |
| **3.5 Variant readings** | `aeon/variants/` (apparatus/prompts/selector/engine), `schemas/apparatus_v1.json`, Detective mode `reading`, work-guard, v2 traces | `1522365`, `9e89dac` |
| **3.3 Gold-standard** | `gold/` (49 записей / 12 текстов; schema 1.1.0→1.1.1; annotators.json; metrics.md) + `aeon/gold/` (loader/metrics/runner/report) | цикл 3.3 + `1875319` |
| **Экспансия gold** | +6 текстов (pindar/sophocles/sappho16/cicero/vergil/rgda), морфо-разметка 224 формы, retroactive Phase A | `1875319`, `36b855b` |
| **3.2 Morphology** | `aeon/morphology/` (morph_v1: enum-synced контракт, completeness-verify, budget-scaling, finish_reason-retry); baseline morph_t4 | `a04e57d`…`5f87b83` |
| **Maintenance-цикл** | аудит 15 LLM-sites; linguistics truncation fix; budget 2000→4000; 9×`except:pass` cleared; 3 CI-guards; deprecation warnings + CHANGELOG | `a3927ca`…`fb1cb8f` |

## 2. Baselines (сводка)

| Слой | Метрика | Значение | Источник |
|---|---|---|---|
| Extraction (real t4, 49 атомов) | Entities F1 | **0.78** (P .65 / R .97); core-6 fold 0.82; caesar/plato/sophocles/fr16 = 1.00 | `gold/reports/real_2026-10-14_t4.md` |
| Verification (real t4) | detective / expert / logician | **0.88** / 1.00 / 1.00 | там же |
| Markers / is_fragment / MAE | | 1.00 / 1.00 / 0.09 | там же |
| Morphology (morph_t4, 28 атомов/224 формы) | pos .98 · lemma .92 · tense .96 · mood .98 · voice .93 · person .90 · case .99 · number .99 · gender .98 | | `gold/metrics.md` |
| Стоимость | full-gold (49×extract+24×verify) **$0.0228** / 167 s; morph $0.0214 / 73 s; cache-hit работает (50K токенов) | | отчёты |
| Latency | ~2.3 s/вызов (extract+verify); ~2.6 s/вызов (morph) | | |

## 3. Design principles #1–#6 (сведены)

1. **`finish_reason` проверяется во всех LLM-вызовах** (провайдер): `length` →
   `llm_output_truncated` + retry ×2; `max_tokens` масштабируется по input.
2. **Для каждой категории в enum'ах промпта — few-shot пример** (3 случая:
   adj/adjective, participle, imperative).
3. **Gold — не догма:** эволюция только через source-verified патчи
   («было/стало/почему»), не подгонка под model (Class A 1.1.1).
4. **F1 vs gold-diff:** рост F1 может быть bad, падение — good; отчёт без
   gold-diff — не отчёт (worked example #2: person 0.97→0.90).
5. **Behavioral rule → CI-guard** (иначе правило нарушается; guards:
   `tests/test_llm_guards.py`).
6. **Behavioral scans — AST, не regex/string** (линейный скан дал 0, AST — 12;
   инструмент проверки обязан быть корректнее проверяемого).

## 4. Backlog (с триггерами)

| Item | Триггер | Примечание |
|---|---|---|
| Contract v1.1 (drop `name=null` entities; pronoun-person few-shot; Doric/derivational lemma примеры) | case-based: расширение pronoun/Doric-покрытия или ≥3 форм класса | trigger-gated, НЕ активирован |
| 3.9 embeddings-provider | failing case / измерение необходимости | deferred |
| `json_repair` strategy-loop refactor | новый edge-case repair ИЛИ logging-критичность | named debt (3× frozen-baseline pass) |
| Legacy v3.0 facade removal | после следующего major | warnings+CHANGELOG добавлены (`fb1cb8f`) |
| `call_structured` (dynamic budget + has_more chunking) | Ф4 | Google-AI-consult; кейс: linguistics 124 findings |
| `report.py` coverage (53%, CLI) / Finding#4 display | minor backlog | |
| `anchor_language` inference / mock-fixtures alignment | minor backlog | |
| Threshold 0.85 min-vs-avg calibration | Ф4 | данные собраны (2 атома, defer) |

## 5. Остаток Ф3 — решения checkpoint'а

- **3.4 cross-references — АКТИВЕН следующий**: требует **нового типа gold**
  (межтекстовые связки) → **Plan Mode scoping до кода** (критерии, стоп-точки,
  объём gold-расширения).
- **3.6 Web UI/API — defer** до завершения 3.4 (решение внутри 3.4-плана).
- **3.7 export formats — кандидат после 3.4** (малый, low-risk).
- **3.8 calibration — Ф4** (по исходному roadmap).
- Новые побочные треки (legacy-deprecation, strategy-loop) — не в Ф3-скоупе.

## 6. Процесс

Кураторские стоп-точки; verification-before-completion; отчёты по 4 частям;
каждый шаг — contract-cycle (rules → few-shot → стоп-точка → код → measurement).
Suite: **428 passed** (2 deselected, 2 xfailed).
