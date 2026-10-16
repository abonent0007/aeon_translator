---
name: logos-semantic-analysis
description: Семантический анализ древних текстов (grc/la) через CLI — extract+verify, morphology, crossrefs, variant readings, детерминированный экспорт TEI/MD/JSON-LD/BibTeX. Триггеры — logos, семантический анализ, древний текст, run_aeon, aeon.demo, .aeon, crossrefs, TEI export.
---

# LOGOS Semantic Analysis — agent CLI

Программа: `C:\Users\User\Documents\aeon_translator-main\aeon_translator-main`.
Вход — тексты на **grc** (древнегреческий, −800…600) / **la** (латынь, −200…1800).
Выход — структурированный анализ `.aeon v2` + отчёты (TEI/Markdown/JSON-LD/BibTeX).
Работает offline (mock, 200 ms/вызов) и онлайн (`--real`, DeepSeek, ключ в `.env`).

## Жёсткие правила

1. **Всегда с аргументами.** Вызов `run_aeon.bat` БЕЗ аргументов открывает
   интерактивное меню и БЛОКИРУЕТ stdin. Для агента: `run_aeon.bat <cmd> ...`.
2. Рабочая директория = корень репозитория (иначе относительные пути и `.env`
   не найдутся): `cd /d C:\Users\User\Documents\aeon_translator-main\aeon_translator-main`.
3. `demo` без `--text` — тоже интерактивное меню. Всегда передавай `--text FILE`.
4. stdout — источник правды; **exit code ≠ 0 = ошибка** (2 = неизвестная команда).
   Не выдумывать результаты.
5. Стоимость: `--real` расходует API-кредиты (~$0.02–0.04 за короткий прогон).
   Без `--real` — бесплатный mock.
6. Не печатать содержимое `.env` (секреты).

## Команды

| Команда | Назначение |
|---|---|
| `run_aeon.bat help` | список команд, exit 0 |
| `run_aeon.bat demo --text FILE --language=grc [--verify=off\|basic\|full] [--real] [--save-aeon OUT.aeon] [--layers=all] [--focus=all] [--reconstruct]` | анализ текста |
| `run_aeon.bat export --aeon IN.aeon --format tei\|md\|jsonld\|bib --out DIR [--bib-split off]` | экспорт (байт-детерминированный) |
| `run_aeon.bat crossrefs --a FILE_A --b FILE_B [--author-a X --author-b Y] [--real] [--json-out OUT]` | кросс-ссылки пары текстов |
| `run_aeon.bat gold --dataset gold/annotations/ --mode mock` | gold-метрики (offline) |
| `run_aeon.bat test [-k EXPR]` | тесты (`python -m pytest -q`), gate перед правками |
| `run_aeon.bat web` | web-дашборд (блокирующий; http://localhost:8080) |

## Типовые сценарии

**Анализ (offline mock):**
```
run_aeon.bat demo --text examples/greek/plato_apologia_17a.txt --verify=full --language=grc
```
Parse-точки stdout: `АТОМ: Atom(<hash> | <intent> | <domain> | N ent)`,
`CVI: <v> | вердикт: <verified|abstained|contradicted>`, сущности, маркеры.

**Анализ real + сохранение + экспорт:**
```
run_aeon.bat demo --text my_text.txt --language=grc --verify=full --real --save-aeon out.aeon
run_aeon.bat export --aeon out.aeon --format md --out exports/
```
Экспорт отклоняет gold-JSONL по дизайну (predictions only).

**Regression перед правками проекта:** `run_aeon.bat test`
(полный набор — 480 тестов; baseline поведения: `python tools/baseline_capture.py` → diff с `baseline.json`).

## Ограничения (не обещать больше)

- Поддерживаются только `grc` и `la`.
- Маркеры (лакуны и т.п.) не персистятся в `.aeon v2` — TEI без `<gap/>`.
- Mock-режим `--verify` иллюстративный (canned-ответы старше v1-контракта):
  абстенция в mock нормальна; «verified»-показатели брать из `--real`.
- Crossrefs: source = хронологически ранний текст; `--author-*` отключает
  same-author пары (одноавторские связи не cross-refs).
- `web`/`cli` — блокирующие интерактивные процессы; агент их не запускает без
  явной необходимости.
