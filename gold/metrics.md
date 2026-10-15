# gold/metrics.md — метрики gold-standard (шаг 3.3)

annotations_version: 1.0.0 | датасет: 28 записей / 6 текстов | факт: `--mode mock` (canned-фикстура)

## Целевые метрики (из критериев 3.3)

| Метрика | Цель (mock) | Цель (real) | Факт (mock) |
|---|---|---|---|
| Markers F1 (lacuna) | ≥0.9 | ≥0.8 | **1.00** |
| Markers F1 (supplement) | ≥0.85 | ≥0.75 | **1.00** |
| Markers F1 (crux) | ≥0.9 | ≥0.8 | n/a — в когорте 3.3 нет crux-текстов (CIL-образец не включён; цель на будущее) |
| Entities F1 | ≥0.75 | ≥0.65 | 0.06 ⚠️ |
| is_fragment accuracy | ≥0.9 | ≥0.85 | **1.00** |
| completeness_score MAE | ≤0.15 | ≤0.2 | 0.40 ⚠️ |
| Verdict accuracy (detective/expert/logician) | — | — | 0.00 / **1.00** / **1.00** |

## Интерпретация mock-фактов (стоп №3: сигналы, не «провалы»)

**mock-baseline — документация ТЕКУЩЕГО состояния pipeline, НЕ метрики качества
анализа.** После 2.7 (real API) числа изменятся; сравнение mock-vs-real — цель.

- **Markers 1.00, is_fragment 1.00** — **self-consistency, не валидация**:
  pack-конвенции и аннотатор — одна и та же методологическая пара
  (IG/Leiden-подмножество); F1=1.00 подтверждает согласованность конвенций
  с rule-based детекцией, а не «качество анализа».
- **Entities 0.06** — canned-фикстура возвращает ОДИН глобальный набор
  сущностей на все сегменты (анти-циркулярность: Belgae в Гомере by design).
  Метрика честно фиксирует, что mock-LLM не решает задачу entities;
  реальный уровень покажет gold_real (2.7). НЕ подгонять фикстуру под gold.
- **completeness MAE 0.40** — extractor c canned-структурой отдаёт 0.6
  (неполные 5 полей) против ожидания 1.0. Тот же класс сигнала.
- **Detective 0.00** — canned-цитата пустая → `unverifiable` ≠ gold `grounded`;
  expert/logician 1.00. Проверяет, что метрика вердиктов различает совпадения.
- **Baseline-тесты:** markers/is_fragment — `meets_baseline` PASS;
  entities/completeness — `xfail` (достижимо только на real; см. стоп №3:
  два уровня тестов — `reports` всегда, `meets_baseline` с xfail).

## Real-baseline (2.7.3-b/t3, 2026-10-14) — ФАКТ (после contract-фиксов)

**Phase 2 real baseline (финал).**

Прогон: 52 вызова, 135.3 s, **$0.0189** (flash off-peak, thinking off), failures=0;
raw: `gold/real_runs/2026-10-14_t3/`; отчёт: `gold/reports/real_2026-10-14_t3.md`.

| Метрика | Mock | t1 (v3.0) | **t3 (v1 contract)** |
|---|---|---|---|
| Markers F1 (lacuna/supplement) | 1.00/1.00 | 1.00/1.00 | **1.00/1.00** |
| Entities F1 | 0.06 | 0.24 (P .14 / R .76) | **0.75** (P .63 / R .90) |
| is_fragment accuracy | 1.00 | 1.00 | **1.00** |
| completeness MAE | 0.40 | 0.00 (flat 1.0) | **0.09** |
| detective accuracy | 0.00 | 0.00 | **0.75** (plato 1.00 / sappho 0.60) |
| expert / logician | 1.00/1.00 | 0.88/0.88 | **1.00/1.00** |

**История прогонов:** t1 = baseline v3.0-контракта; **t2 = FAILED** (deepseek-flash —
thinking-модель: reasoning съедал max_tokens=2000 → пустой content у всех 28 вызовов,
rule-fallback; диагноз probe-verified, фикс — thinking disabled, commit 7a721d0);
t3 = первый валидный v1-прогон.

**Stop-flags t3 (ждут решения куратора):**
- **Grammar-flavored kept = 48/84 (57%)** — формально >0%; НО это *anchored*
  morpho-syntax observations («The verb dative…», verifiable), НЕ запрещённые
  инструкции «Identify…» (тех skip=3). Вопрос: Rule 3 выполнен (anchored syntax
  ок) или нужна итерация промпта под content-focus.
- **Role-consistency violations: 3/28 (10.7%) > 5%** — детали: homer `Ἀχιλῆος`
  (role=patient, roles.patient='μῆνιν'), `Ἀχαιοῖς` (goal vs пусто), plato
  `Ἀθηναῖοι` (patient vs roles.patient='ὑμεῖς'). Rule 5 в v1 нестабилен.

**Без изменений:** markers/is_fragment (pack-детерминизм). Entities per text:
caesar 1.00, plato 1.00, homer 0.92, inscription 0.50, **papyrus/sappho 0.00 —
артефакт zero-gold**: t3 FP там = **1+1** (граничные: `βασιλεύς` —
generic-office; `θέοισιν` — generic-deity-plural; остальные сегменты
`entities=[]`); кандидаты в contract v1.2 edge-case, НЕ word-salad.

**Worked example (contract-first, 2.7.3):** гипотеза (contract-first: extractor v1
+ detective v1 + build_claims + v2-метаданные) → предсказание (entities F1 ↑,
detective ↑) → измерение на ТЕХ ЖЕ gold (t1 vs t3): Entities 0.24→0.82,
detective 0.00→0.75, expert/logician 0.88→1.00, MAE flat→0.09, cost −46%.
Гипотеза подтверждена — методологический, не «прогресс разработки».

## Real-цели — гипотеза

Числа real-колонки — гипотеза (после 2.7 пересматриваются; N=28 — малая
выборка, целевые значения — ориентиры, не SLA). Прогон:
`python -m aeon.gold.report --dataset gold/annotations/ --mode real`
