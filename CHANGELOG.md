# Changelog

## Unreleased

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
