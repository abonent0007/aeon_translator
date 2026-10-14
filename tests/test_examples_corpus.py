"""Regression: файлы корпуса examples/ соответствуют заявленному языку.

Аудит 3.3 (RU-флаг): `examples/greek/plato_apologia_17a.txt` был RU-конспектом
(артефакт Ф1), но использовался как grc-вход. Эти тесты не дают дефекту вернуться.
Диапазоны: Greek and Coptic (0x0370–0x03FF) + Greek Extended (0x1F00–0x1FFF);
кириллица 0x0400–0x04FF в греческий диапазон НЕ входит.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GREEK_MIN_BODY = 50   # греческих букв минимум (заголовки/примечания — кириллица)
LATIN_MIN_BODY = 50
GREEK_MAX_IN_LATIN = 5


def _counts(text: str):
    grc = sum(1 for c in text
              if 0x0370 <= ord(c) <= 0x03FF or 0x1F00 <= ord(c) <= 0x1FFF)
    cyr = sum(1 for c in text if 0x0400 <= ord(c) <= 0x04FF)
    lat = sum(1 for c in text if 0x0041 <= ord(c) <= 0x007A)
    return grc, cyr, lat


def test_greek_examples_contain_greek_body():
    """Каждый *.txt в examples/greek/ (кроме legacy/) — с греческим телом."""
    files = sorted((REPO / "examples" / "greek").glob("*.txt"))
    assert files, "корпус examples/greek пуст?"
    for path in files:
        grc, cyr, _ = _counts(path.read_text(encoding="utf-8"))
        assert grc >= GREEK_MIN_BODY, (
            f"{path.name}: греческое тело отсутствует (grc={grc}, cyr={cyr}) — "
            f"RU-конспект? См. legacy/"
        )


def test_latin_examples_contain_latin_body_without_greek():
    """Каждый *.txt в examples/latin/ — с латинским телом и без греческих букв."""
    files = sorted((REPO / "examples" / "latin").glob("*.txt"))
    assert files, "корпус examples/latin пуст?"
    for path in files:
        grc, _, lat = _counts(path.read_text(encoding="utf-8"))
        assert lat >= LATIN_MIN_BODY, f"{path.name}: латинское тело отсутствует (lat={lat})"
        assert grc <= GREEK_MAX_IN_LATIN, (
            f"{path.name}: неожиданные греческие буквы (grc={grc})"
        )
