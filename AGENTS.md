# AEON v4.0 «Deep Analyst» — Project Guide

## Overview
Semantic processor: переводит смысл между формами (текст/код/эмоция/голос/изображение)
с верификацией, entity linking и анализом древних текстов.
Статус: **Фаза 0 ✅, Фаза 1 ✅, Фаза 2 — шаги 2.0 ✅, 2.1 ✅** (Language Pack Infra,
Ancient Greek Pack). Впереди: 2.2 Latin Pack, 2.3 Fragment Hypotheses,
2.4 Linguistic Layers, 2.5 Multi-focus, 2.6 Offline adapters, 2.7 Real API.

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

## Language Pack Architecture (Фаза 2)
Контракт (`aeon/language/base.py`): ABC `LanguagePack` — `iso_code`,
`display_name`, `period` (BCE — отрицательные), `direction`,
`special_tokens` {lacuna, editorial} (значение — строка ИЛИ список вариантов),
`prompts` {extract, verify, reconstruct}, `dictionaries`, `unicode_ranges`;
методы: `detect_markers` [abstract], `normalize` [NFC default], `is_fragment`,
`validate` (fail-fast контракт).

Реестр (`aeon/language/registry.py`): `register` — eager-регистрация фабрики,
lazy-инстанциация + validate при первом `get` (инстанс валидируется сразу);
`force=True` — осознанный override; `get` — KeyError со списком; `list_available`
(sorted); `detect` — по `unicode_ranges`, **tie-break детерминирован
(алфавитный iso_code) + событие `detect_ambiguous`**; `clear` — тесты.

Как добавить пак: подкласс `LanguagePack` (реализовать `detect_markers`) →
`registry.register(PackClass)`; builtin-паки регистрируются в
`aeon/language/__init__.py` (класс, инстанциация ленива).

Политика нормализации (refinement 2.0 №2): нормализуется только
**pipeline-вход**; оригинальный текст пользователя сохраняется в
`result["source"]["content"]` (см. тест `test_translate_original_content_preserved`).

Приоритет маркеров: `pack.special_tokens` — приоритетный источник;
`semantic_atom.LACUNA_MARKERS` — fallback, когда pack=None (интеграция
в extractor — шаги 2.3+).

## Ancient Greek Pack (шаг 2.1)
`aeon/language/grc.py` — `grc` (Ancient Greek, period −800..600).

Конвенции маркеров (подмножество Leiden/SIG): `lacuna` — `[...] […] [lacuna]
[---]`; **`supplement` — контекстное правило (стоп-точка 2.1 №1)**: скобки с
буквами (`[Ἀθῆναι]`, `[Ἀριστ]είδης`) → supplement; скобки с точками/тире →
lacuna; `editorial` — `<...> <*>`; `deletion` — `{...}`; `uncertain` —
`(...) [...?]`.

Нормализация (стоп-точка 2.1 №2, решения): NFC (дыхания/диакритика
СОХРАНЯЮТСЯ — семантичны: ἡ ≠ ἠ); конечная сигма ς **не** унифицируется с σ;
iota subscript (ᾳ/ῃ/ῳ) **не** разворачивается в adscript. Обоснование —
Unicode-стандарт + практика изданий Perseus/TLG (стандартная орфография);
поисковые унификации — отдельный слой Ф3.

Промпты (`extract`/`verify`/`reconstruct`, ≤30 строк): явно ссылаются на
маркеры; `reconstruct` — 2–4 гипотезы + обязательный путь
`no_reconstruction_possible` (max confidence < 0.5).

Ограничения: морфологии нет (Ф3, Morpheus — интерфейс-хук); древний и
новогреческий по codepoints не различаем (кандидат от `detect`).

Эталонные тексты: `examples/greek/` — 5 фрагментов (Plato Apologia,
Homer Il. 1.1–7, надпись с лакунами, папирус с лакунами, Sappho fr. 31)
+ `LICENSE.md` (public domain; копии оцифровок Perseus/PHI сознательно
не использовались — стоп-точка 2.1 №4; per-file атрибуция — Ф2.6).

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
- Тесты: `python -m pytest -q` (live: `pytest -m network -k pleiades`)
- Coverage (обходной раннер — см. quirks): `python tools/run_coverage.py`
- Demo верификации: `python -m aeon.demo --text examples/greek/plato_apologia_17a.txt --verify=full --language=grc`
  (mock 200ms/вызов; `--real` — с DEEPSEEK_API_KEY; `--verify=off|basic|full`;
  `--language` — ISO-код пака: нормализация + маркеры)
- verify_mode в API: `translator.translate(..., verify_mode="off|basic|full", language_pack=None)`
  (legacy `verify=True` ≡ `verify_mode="full"`)
- Реестр паков: `python -c "from aeon.language import registry; print(registry.list_available())"`
  → `['grc']` (Latin — 2.2)

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
- **Verification 2.0 (точная формула CVI — для воспроизводимости):** negatives
  доминируют → `contradicted` (conf = max по негативным); нет positives →
  `abstained` (conf 0.0); **CVI = среднее confidence ПОЛОЖИТЕЛЬНЫХ вердиктов**
  (round 4; нейтральные/abstained в среднее НЕ входят); CVI < 0.50
  (`abstention_threshold`) → `abstained`; needs_review при CVI < 0.85
  (=1−`legacy.risk_verified_max`). Пример: mean(0.91, 0.90) = 0.905 →
  в выводе `{cvi:.2f}` отображается «0.91». Per-agent abstention (detective
  conf<0.85, logician coherence<0.60); logician при <2 claims — abstained.
- **verify_atom:** legacy-ключи (consistency/grounding/hallucination_risk/
  overall_verdict) + v4.0 (agents/combined/cvi/abstained/reasoning_trace).
- **LanguagePack (Ф2):** вариант A (промпты + словари + special tokens;
  морфология — Ф3); stdlib-only (`unicodedata`); detect() — декларативные
  `unicode_ranges`; registry — eager-регистрация + lazy-инстанциация.
- **Нормализация пака — только pipeline:** оригинал сохраняется в
  `result["source"]["content"]` (refinement 2.0 №2).

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
- **Coverage-раннер — кросс-платформенный:** `tools/run_coverage.py` использует
  только Coverage API, валиден и на Linux (там штатный `pytest --cov` тоже
  работает); версия закреплена `coverage>=7.4,<8.0` в requirements-dev.
- **Network-тесты в CI (план):** `pytest -m network` — отдельная НЕблокирующая
  джоба; локально — по требованию; Pleiades live-тест skip при недоступности.
- **Real-API gap:** demo-метрики на mock (200 ms/вызов — экстраполяция); реальный
  DeepSeek ≈1.5–4 s/вызов → 4 вызова ≈6–16 s; Ф2 multi-focus (до 12 вызовов)
  может потребовать параллелизации (backlog шаг 2.7).
