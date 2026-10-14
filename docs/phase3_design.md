# Phase 3 Design — kickoff (AEON v4.0)

## Order
**3.1 `.aeon v2` → 3.5 variant readings → 3.3 gold-standard corpus**
(3.2 morphology — только после gold-standard И 2.7; 3.6 web — после 2.7;
3.4/3.7/3.8 — backlog.)

Почему такой порядок: v2 проектируется с **явным слотом** под variant
readings (3.5 заполняет слот, не расширяя формат); gold-standard —
инструмент валидации, ему нужно что валидировать.

## 3.1 — контракт `.aeon v2` (схема: `schemas/aeon_v2.json`)
- Обязательные: `aeon_version` (^2.x), `created_at`, `generator`, `source`,
  `atom`, `traces`, `metadata.thresholds_snapshot`, `metadata.mock`.
- Forward-slots в `traces`: extraction/entity_linking/verification/
  linguistics/focus/reconstruction + зарезервированные
  `variant_readings`(3.5)/`morphology`(3.2)/`cross_references`(3.4) = null.
- `source.content` = ОРИГИНАЛ; `source.normalized` = pipeline-вход.
- `mock: true` обязателен до 2.7 (научная чистота: mock-прогон помечен).
- Версионирование semver: 2.1+ — опциональные поля в `extensions`; 3.0 — breaking.
- Backward read: v1-файл читается и представляется как v2 в памяти
  (`extensions.legacy_v1_original`), запись — только v2.
- Валидация: **stdlib-мини-валидатор** (required/types/const/pattern) —
  собственный, без пакетов jsonschema.

## Preflight 3.5 — variant readings (answers)
1. **Источник чтений:** (b) — LLM только ВЫБИРАЕТ между внешне заданными
   attested readings; генерация из головы запрещена (Sappho-урок).
2. **Формат apparatus:** sidecar-JSON на произведение:
   `{"work", "editions":[{"edition","year"}], "loci":[{"line",
   "readings":[{"text","editions":["Voigt"],"note"}]}]}`;
   CLI `--variant-readings PATH`, API-параметр.
3. **Отличие от 2.3:** отдельный движок `aeon/variants/` (mode=select);
   2.3 = генерация из контекста, 3.5 = выбор среди засвидетельствованного;
   общий engine не делаем.
4. **Attribution обязателен:** каждое чтение цитирует издание(я);
   чтение без издания отклоняется (validation error). Выход несёт
   выбранное издание.
5. **Флаги:** отдельный `--variant-readings`; независим от `--reconstruct`;
   при наличии в тексте и лакун, и вариантов — оба блока в `traces`.
   Если max(confidence выбора) < 0.5 → `no_selection_possible` (аналог 2.3).

## Preflight 3.3 — gold-standard corpus (answers)
1. **Источник разметки:** (c) гибрид; фактически старт — ручная аннотация
   5 отрывков (treebanks AGDT/PROIEL — опционально при доступе из сети).
2. **Granularity:** marker + atom-level — все 5; finding/insight-level —
   1–2 отрывка (Homer findings; Sappho — variants/reading-slot).
3. **Метрики:** markers P/R/F1 (per kind + macro); entities F1;
   is_fragment accuracy; findings accuracy (на аннотированных);
   focus insight — human binary check (backlog, не Cohen's κ сейчас).
4. **Лицензия:** CC0 (данные корпуса; исходные тексты PD).
5. **Формат:** JSONL expectations + README (`gold/`).
6. **Mock vs real:** маркеры pytest `gold_mock` (CI, регрессионный baseline)
   и `gold_real` (нужен ключ; качество vs ground truth).

## 2.7 trigger policy
- Ключ появился ДО 3.1 → пауза Ф3, делаем 2.7 (может изменить v2-схему:
  cost/latency поля).
- Во время 3.1/3.5/3.3 → `key_available: true, defer_2_7: true`, продолжаем.
- После 3.3 → 2.7 приоритетно над 3.2/3.4/3.6/3.7.
- Без real-API-валидации **не стартовать 3.2** (точность не измерена).

## Not in scope (Ф3)
- Раздувание языковых паков (Medieval Latin, Coptic, Sanskrit) до gold-standard.
- «AI-агент, который сам исследует тексты» (marketing, не research).
