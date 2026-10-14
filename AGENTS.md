# AEON v4.0 «Deep Analyst» — Project Guide

## Overview
Semantic processor: переводит смысл между формами (текст/код/эмоция/голос/изображение)
с верификацией, entity linking и анализом древних текстов.
Статус: **Фаза 0 ✅, Фаза 1 ✅** (рефакторинг v3.0 → v4.0). Фаза 2 — впереди
(паки древних языков: др.-греческий, латынь; fragments/multi-focus).

## Architecture (Фаза 1)
```
текст ──► MeaningExtractor (LLM-структура + rule fallback)
      ──► SemanticAtom (+ фрагменты: is_fragment / completeness / needs_attention)
      ──► Entity Linking: Wiki data (search→fetch; cache 7д; merged-QID healing)
      │                   └─► external_ids: wikidata / pleiades(P1584) / trismegistos(P11651)
      ──► Verification 2.0 (verify_mode: off|basic|full):
      │     Detective (grounding/цитаты) · Expert (факт-чек) · Logician (coherence)
      │     └─► Aggregator: CVI + calibrated abstention (≥0.50, иначе «Я не знаю»)
      ──► Generator / .aeon v1 (reasoning trace — в v2, Фаза 3)
```

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
- MockLLM — в `aeon/testing.py` (общий с demo; `latency_ms` имитирует сеть)

## Commands
- Тесты: `python -m pytest -q` (141 passed; live: `pytest -m network -k pleiades`)
- Coverage (обходной раннер — см. quirks): `python tools/run_coverage.py`
- Demo верификации: `python -m aeon.demo --text examples/plato_sample.txt --verify=full`
  (mock 200ms/вызов; `--real` — с DEEPSEEK_API_KEY; `--verify=off|basic|full`)
- verify_mode в API: `translator.translate(..., verify_mode="off|basic|full")`
  (legacy `verify=True` ≡ `verify_mode="full"`)

## Key Decisions
- **Config access (канонический):** `CONFIG.verification.detective` — иерархический;
  плоский `CONFIG.detective` — convenience-алиас (новый код — только иерархический).
- **Дефолты конфига = поведение v3.0 1:1** (`aeon/config.py`;
  `legacy_config_used_by`: legacy-проекция risk-полос + review-threshold агрегатора).
- **LLM-слой:** пакет `aeon/llm/`; `from aeon.llm_client import DeepSeekClient` — shim.
- **Ретраи:** backoff + `Retry-After` (max); retryable = 5xx/408/429/timeout/connection.
  `llm_call.latency_ms` = все попытки (включая backoff-паузы), поля attempts/retries.
- **JSON-repair:** только stdlib (fences, скобки, trailing commas, ast). При неудаче
  канал v3.0: `{"raw_response", "parse_error"}` + лог; extractor → rule-fallback.
- **Entity Linking:** opt-in (`AEON_ENTITY_LINKING=1`; contact_email обязателен при
  включении — fail-fast). Wikidata Action API, UA с контактом, rate limit ≤1 rps,
  SQLite-кэш 7д, offline-режим; веса скоринга — `AEON_SCORE_WEIGHT_*`.
- **Fragment-понятия ортогональны:** `is_fragment` — свойство ИСТОЧНИКА (лакуна);
  `completeness_score` — качество ИЗВЛЕЧЕНИЯ (5 полей); агрегат `needs_attention`.
- **Verification 2.0:** negatives доминируют → `contradicted`; нет positives →
  `abstained`; positives-mean <0.50 → `abstained`; needs_review <0.85; нейтральные
  НЕ штрафуются; per-agent abstention (detective conf<0.85, logician coherence<0.60);
  logician при <2 claims — abstained (без false positive).
- **verify_atom:** legacy-ключи (consistency/grounding/hallucination_risk/
  overall_verdict) + v4.0 (agents/combined/cvi/abstained/reasoning_trace).

## Known Quirks & Limitations
- **Wikidata:** ошибки API = HTTP 200 + `{"error": {...}}` (не HTTP-код!). Каждый
  новый клиент обязан различать HTTP-ошибки и API-error-payload.
- **Trismegistos:** публичного API нет (SSL-цепочка + 403 анти-бот) → stub
  (`no_public_api`); датасеты — Фаза 2.
- **Pleiades:** недоступен из dev-сети (TCP ok, нет ответа) → защитный парсер +
  live-тест `pytest -m network -k pleiades`; offline dump adapter — Фаза 2.
  Клиент ходит только по hostname.
- **Детектив ↔ переводы:** exact-quote работает лишь с исходным языком; для
  переводов — `unverifiable_due_to_missing_data` (нейтрально). `allow_translation_match` — Ф2.
- **Expert:** различие `no_external_data` vs `external_data_silent` пока отсутствует (Ф2).
- **Coverage на Windows:** pytest-cov (`--cov`) падает access violation (0xC0000005)
  при загрузке torch DLL. Обход: `python tools/run_coverage.py` (Coverage API
  стартует до pytest). Не возвращаться к `pytest --cov`.
