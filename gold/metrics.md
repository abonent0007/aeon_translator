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

## Real-baseline (2.7.3, 2026-10-14) — ФАКТ

Прогон: 52 вызова, 155.9 s, **$0.0351**, failures=0; raw: `gold/real_runs/2026-10-14_t1/`;
отчёт: `gold/reports/real_2026-10-14.md`.

| Метрика | Mock | **Real** | Комментарий |
|---|---|---|---|
| Markers F1 (lacuna) | 1.00 | **1.00** | pack-детекция детерминированна (не LLM) |
| Markers F1 (supplement) | 1.00 | **1.00** | то же |
| Entities F1 | 0.06 | **0.24** (P 0.14 / R 0.76) | recall высокий — имена находятся; precision убита словесным шумом |
| is_fragment accuracy | 1.00 | **1.00** | pack |
| completeness MAE | 0.40 | **0.00** | extractor всегда отдаёт 1.0 — поле не калибровано (finding) |
| Verdicts detective | 0.00 | **0.00 ⛔ стоп №4** | root-cause найден (ниже), НЕ «сломан exact-quote» |
| Verdicts expert | 1.00 | **0.88** | |
| Verdicts logician | 1.00 | **0.88** | |

**Стоп №4 (detective <0.3) — сработал, диагноз по raw:** exact-quote РАБОТАЕТ
(quote_in_source 7/7 на всех сегментах), ломается КОМПОЗИЦИЯ claims:
(1) real `explanation_chain` = грамматические инструкции («Identify the main
verb…»), а не семантические утверждения; (2) принудительные meta-claims
`Intent:`/`Domain:` почти всегда возвращаются с пустой цитатой →
`grounded_count < total` (all-or-nothing, detective.py:135) → unverifiable;
(3) даже при 7/7 (sappho seg3) avg conf 0.83 < min 0.85 → abstained.
Это контрактный дефект claims + оптимизм gold-ожиданий (annotator ставил
`grounded` до real-данных) — материал для решения куратора, НЕ фикс.

**Entities — разбор (raw):** (a) извлечение = «словесный салат»: местоимения,
служебные слова и АНГЛИЙСКИЕ переводы (`truth`, `king`, `sitting`) как entities;
(b) метрик-артефакт: grave/acute не совпадают при casefold (`Διός` vs `Διὸς`,
`Ἀκαμαντίς` vs `Ἀκαμαντὶς`) — нужен accent-insensitive матч; (c) расширение
спанов артиклями/патронимиками (`ὁ Ἀθηναίων`, `Πηληϊάδεω Ἀχιλῆος` vs `Ἀχιλῆος`).
Лучший текст: **caesar 0.73** (реальные имена, FPs — 3 общих слова).

## Real-цели — гипотеза

Числа real-колонки — гипотеза (после 2.7 пересматриваются; N=28 — малая
выборка, целевые значения — ориентиры, не SLA). Прогон:
`python -m aeon.gold.report --dataset gold/annotations/ --mode real`
