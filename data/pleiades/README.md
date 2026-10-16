# data/pleiades/ — Offline-дамп Pleiades (шаг 2.6)

Здесь лежит дамп Pleiades, сконвертированный в **JSONL-формат LOGOS**
(данные НЕ коммитятся; этот README — в репо).

## Как подготовить дамп

1. Скачайте официальный Pleiades bundle (JSON/CSV, https://pleiades.stoa.org/downloads)
   один раз вручную (контроль версии и воспроизводимость).
2. Сконвертируйте его в JSONL LOGOS-формата:
   - строка 1 — meta:
     `{"meta": {"source": "pleiades", "dump_version": "<версия>", "dump_date": "<ISO>", "license": "<из LICENSE бандла>", "license_file_sha256": "<SHA256 LICENSE-файла>"}}`
   - далее по одной записи на строку:
     `{"id": "...", "title": "...", "place_types": [...], "repr_point": [lon, lat], "uri": "...", "dump_version": "..."}`
3. Посчитайте SHA256 LICENSE-файла бандла (Windows):
   `certutil -hashfile LICENSE SHA256` — это доказательство лицензии
   (`provenance().license_file_sha256`); adapter откажется загружать дамп без него.

## Атрибуция

Pleiades документирует лицензию **CC BY 3.0**; финальное подтверждение
берётся из LICENSE-файла самого бандла (поле `license` в meta) — не из памяти.

## Пример

`tests/fixtures/dumps/pleiades_sample.jsonl` — 5 записей (Athenae, Alexandreia,
Roma, Ephesos, Carthago) для mock-тестов.
