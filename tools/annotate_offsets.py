"""
Утилита gold-аннотаций (шаг 3.3): поиск offset'ов маркеров + валидация.

Зачем: bookkeeping при добавлении сегментов — «добавил текст маркера →
получи offset → вставь в JSONL». Для строчных сегментов (эпиграфика, папирус,
verse) offset внутри строки = offset внутри сегмента.

Использование:
    python tools/annotate_offsets.py gold/texts/inscription_ig.txt "[...]"
        → все вхождения: (строка, offset в строке, сквозной offset)
    python tools/annotate_offsets.py --check
        → полная валидация gold/annotations/ (схема, integrity,
          offsets каждого маркера, неперекрытие сегментов) — через loader.

Exit code: 0 — ок; 1 — маркер не найден / датасет невалиден.
"""

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def find_offsets(text_file, marker: str):
    """Все вхождения маркера: [(строка, offset_в_строке, сквозной_offset)]."""
    text = Path(text_file).read_text(encoding="utf-8")
    results, start = [], 0
    while True:
        position = text.find(marker, start)
        if position == -1:
            break
        line_number = text.count("\n", 0, position) + 1
        line_start = text.rfind("\n", 0, position) + 1
        results.append((line_number, position - line_start, position))
        start = position + 1
    return results


def check_dataset(annotations_dir=None):
    """Полная валидация датасета (loader) + сводка по текстам."""
    from aeon.gold import load_dataset

    dataset = load_dataset(annotations_dir or REPO / "gold" / "annotations")
    for text_id, records in sorted(dataset.by_text().items()):
        markers = sum(len(record.expected_markers) for record in records)
        entities = sum(len(record.expected_entities) for record in records)
        print(f"  {text_id:24} segments={len(records):2} "
              f"markers={markers:2} entities={entities:2}")
    print(f"OK: {len(dataset.records)} записей, схема {dataset.version()}")
    return dataset


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="gold offsets: поиск и валидация (3.3)")
    parser.add_argument("text_file", nargs="?", help="путь к тексту (gold/texts/…)")
    parser.add_argument("marker", nargs="?", help="текст маркера (напр. '[...]')")
    parser.add_argument("--check", action="store_true",
                        help="валидировать gold/annotations/ целиком")
    args = parser.parse_args(argv)

    if args.check:
        check_dataset()
        return 0
    if not args.text_file or not args.marker:
        parser.error("укажите TEXT_FILE MARKER или --check")
    rows = find_offsets(args.text_file, args.marker)
    print(f"{len(rows)} вхождений {args.marker!r}:")
    for line_number, offset_in_line, global_offset in rows:
        print(f"  строка {line_number}: offset в строке {offset_in_line}, "
              f"сквозной {global_offset}")
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
