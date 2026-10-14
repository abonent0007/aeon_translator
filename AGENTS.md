# AEON v4.0 «Deep Analyst» — Project Guide

## Overview
Semantic processor: переводит смысл между формами (текст/код/эмоция/голос/изображение)
с верификацией, entity linking и анализом древних текстов. Идёт рефакторинг
v3.0 → v4.0 (Фаза 0: фундамент; Фаза 1: Entity Linking + Verification 2.0).

## Tech Stack
- Python 3.11 (Windows dev), приоритет stdlib
- LLM: DeepSeek (OpenAI-совместимый), фасад `aeon.llm.DeepSeekClient`
- Embeddings: sentence-transformers (MiniLM 384D default, LaBSE опц.) — pluggable
- Web: FastAPI + SPA; CLI: REPL (`aeon/cli.py`)
- Формат: `.aeon` бинарный (чтение v1 сохраняется)

## Conventions
- Русские docstrings и комментарии (стиль проекта)
- Новые модули покрываются pytest-тестами; сеть по умолчанию отключена
  (маркеры `network`, `models` — исключены из дефолтного прогона)
- Структурное логирование: `aeon/logging_config.py` → `log_event` (JSON-lines)
- Метрики: `aeon/metrics.py` → `METRICS` (stdlib, без внешних зависимостей)
- Test/dev-зависимости — только в `requirements-dev.txt`

## Key Decisions
- **Config access (канонический путь):** `CONFIG.verification.detective` —
  иерархический. Плоский `CONFIG.detective` — convenience-алиас (только для
  совместимости; новый код использует иерархический путь).
- **Дефолты конфига обязаны совпадать с поведением v3.0 1:1** (`aeon/config.py`;
  легаси-пороги сохранены в `LegacyVerificationConfig`, используются ли — см.
  `orchestrator_state.json → legacy_config_used_by`).
- **LLM-слой:** пакет `aeon/llm/` (base/retries/json_repair/openai_compatible/
  deepseek). `from aeon.llm_client import DeepSeekClient` — рабочий shim.
- **Ретраи:** экспоненциальный backoff + `Retry-After` из ответа
  (delay = max(backoff, Retry-After)); retryable = 5xx / 408 / 429 /
  timeout / connection; прочие 4xx — fail fast.
- **LLM-логи:** `llm_call.latency_ms` — wall-time всех попыток (включая
  backoff-паузы), поля `attempts` и `retries` — для разбора.
- **JSON-repair:** только stdlib-эвристики (fences, скобки, trailing commas,
  `ast.literal_eval`). Внешние json-repair/json5 — не тащим.
- **Entity Linking:** opt-in (`AEON_ENTITY_LINKING=1`, default off);
  Wikidata Action API (2 яруса: `wbsearchentities` → `wbgetentities`);
  UA `AEON-Translator/4.0 (research; contact: ...)`; rate limit ≤1 rps;
  SQLite-кэш 7 дней + маппинг merged Q-ID (old→new); offline-режим
  (`AEON_WIKIDATA_OFFLINE=1`) — только кэш; недоступность источника →
  `source_unavailable=True`, без исключений.
- **Фрагменты (задел):** вердикты различают `unverifiable_due_to_missing_data`
  (нейтрально) и `contradicted` (негативно) — отсутствие данных не штрафуется.
- **Протокол фаз:** кураторские чек-поинты с фиксированным форматом отчёта
  (шаги 0.1–1.4, план и статусы — в `.opencode/orchestrator_state.json`).
