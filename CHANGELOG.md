# Changelog

## Unreleased

### Changed (2026-10-16)
- **Проект переименован: LOGOS Semantic Analysis** (README, DESCRIPTION ×3 языка,
  public summary, AGENTS, gold/data/examples). Проект развился из внутренней
  линии v4.0 «Deep Analyst» (2024–2026); package version — `0.3.0` (фазовая
  карта, pre-1.0). Технические имена (`aeon`-пакет, `.aeon`, `AEON_*` env) —
  без изменений, миграция отдельным решением.
- Внешние endpoint-константы → env-overridable (HARD-001..004:
  `AEON_WIKIDATA_API_URL`, `AEON_PLEIADES_URL_TEMPLATE`, `FLUX_STATUS_URL`,
  `FLUX_TIMEOUT_SEC`; identity-fallback, поведение неизменно, baseline 6/6).
- `setup.py` (легаси-визард) → `setup_wizard.py`; добавлен `pyproject.toml`
  (`pip install -e .`, deps AST-вычислены; extras: web/voice/embeddings/full).
- Статика: `tools/static_scan.py` (unused imports / except-pass / timeout /
  URL-инвентарь); `AGENTS.md` — секция Static analysis (gate: `pytest -q`).

### Added (Фаза 3, 2026-10-10..16)
- `.aeon v2` (writer/reader/validator/migration), morphology (F1 0.90–0.99),
  gold-standard corpus (54 записи/15 текстов, schema 1.2.1), cross-refs engine
  (headline link-F1 0.800), variant readings, export formats (TEI/MD/JSON-LD/
  BibTeX, детерминированные), behavioral baseline tooling, 480 тестов / 92%.

### Deprecated (2026-10-14)
- **Legacy v3.0 фасад `DeepSeekClient`**: `extract_meaning`, `translate_text`,
  `generate_code`, `semantic_compare`, `describe_for_image` — испускают
  `DeprecationWarning`; используйте v4-пайплайн (`aeon.extractor`,
  `aeon.generator`, `aeon.translator`). Удаление — после следующего major.
  Причина: фасад не покрыт тестами (76% coverage модуля) и не используется
  пайплайном; сохранён для внешних потребителей с migration path.

### Fixed (2026-10-14, maintenance-цикл)
- linguistics: output-бюджет 6000 (raw обрезался на 60 findings при 2000) +
  parse_error-accounting (`llm_calls=1`).
- LLM default `max_tokens` 2000 → 4000 (класс «site забыл scale»).
- 9 × `except: pass` устранены (suppress / явные fallback'и); CI-guard
  запрещает новые (frozen baseline: json_repair ×3, strategy-loop — backlog).
- CI-guards: единый SDK-провайдер; AST-скан bare-pass; дефолт-бюджет 4000.
