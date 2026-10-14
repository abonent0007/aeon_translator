# examples/greek/legacy/ — архив (НЕ используется в pipeline и тестах)

Файлы сохранены для истории (Ф1–Ф3.1).

- `plato_apologia_17a_ru_summary.txt` — учебный RU-конспект (артефакт Ф1).
  **Аудит 3.3 (RU-флаг):** файл находился в `examples/greek/` и использовался
  в demo-прогонах как grc-вход, хотя греческого текста не содержал (grc_strict=0,
  cyr=272). Заменён подлинной grc-транскрипцией 17a
  (`examples/greek/plato_apologia_17a.txt`). Regression-защита:
  `tests/test_examples_corpus.py` — файлы вне `legacy/` обязаны содержать
  греческие codepoints.
- `plato_sample_ru_summary.txt` — тот же конспект из `examples/plato_sample.txt`
  (root), нигде не использовался; перенесён для консистентности.
