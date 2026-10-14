# tests/fixtures/aeon_v1/ — frozen v1 artifacts

`legacy.aeon` — **замороженный** v1-файл (доработка D1): создан один раз
production-врайтером v1 на момент шага 3.1 и закоммичен.

Правила:
- файл **не пересоздаётся** в тестах (тест миграции обязан читать
  исторический артефакт, иначе тест циркулярен);
- `test_v1_writer_matches_frozen_fixture` сравнивает текущий v1-writer
  с этим файлом → warning при расхождении (легальная эволюция возможна,
  но должна быть замечена);
- `test_v1_writer_output_still_migrates` — smoke: новый v1-output
  тоже мигрируется.

Содержимое: минимальный атом (Homer, intent=statement, domain=literature,
лакуна в тексте, embedding [0.01,0.02,0.03]).
