"""
AEON Ancient Greek Pack (шаг 2.1) — др.-греческий (ISO 639-3: grc).

Конвенции маркеров (подмножество Leiden/SIG-стиля):
  lacuna      — физический пропуск: [...] […] [lacuna] [---];
  supplement  — восстановление редактором в квадратных скобках С БУКВАМИ:
                [Ἀθῆναι], [Ἀριστ]είδης. Контекстное правило (стоп-точка 2.1
                №1): содержимое скобок — только точки/тире/пробелы → lacuna;
                содержит словоформные знаки → supplement;
  editorial   — редакторские пометки <...> <*>;
  deletion    — подлежит удалению {...};
  uncertain   — неопределённое чтение (...) [...?].

Нормализация (стоп-точка 2.1 №2):
  - Unicode NFC (композиция: дыхания/диакритика СОХРАНЯЮТСЯ — семантичны:
    ἡ (грубое дыхание) ≠ ἠ (тонкое));
  - конечная сигма ς НЕ унифицируется с σ (орфография сохраняется;
    поисковая унификация — отдельный слой, Ф3);
  - iota subscript (ᾳ/ῃ/ῳ) НЕ разворачивается в iota adscript.
  Обоснование: NFC — Unicode-стандарт; практика изданий Perseus/TLG —
  стандартная орфография; транслитерации/унификации — не задача пака.

Ограничения: морфологии нет (Ф3, Morpheus — интерфейс-хук); др.-греческий
и новогреческий по codepoints не различаем (registry возвращает кандидата).
"""

import re
from typing import List

from .base import LanguagePack, Marker

#: Квадратные скобки: содержимое для контекстной классификации.
_BRACKET_RE = re.compile(r"\[([^\[\]]*)\]")
#: Содержимое «пустое» (точки/тире/пробелы/спец-слова) → lacuna, иначе supplement.
_GAP_ONLY_RE = re.compile(r"^[\s\.\-…·]*$")

EXTRACT_PROMPT = """You are analyzing an Ancient Greek text (possibly fragmentary).
Follow the edition's conventions strictly:

1. Gaps: "[...]", "[…]", "[---]", "[lacuna]" mark LOST text (lacuna).
   Bracketed LETTERS, e.g. "[Ἀθῆναι]", are an editorial SUPPLEMENT
   (restored text) — never treat a supplement as certain original text.
2. "<...>"/"<*>" are editorial marks; "{...}" text is to be deleted;
   "(...)" and "[...?]" mark uncertain readings.
3. Never guess or "complete" text inside a lacuna. If the text is
   fragmentary, set is_fragment=true and list every gap.

Return ONLY valid JSON:
{"is_fragment": bool,
 "lacunae": [{"text": "...", "position_hint": "..."}],
 "supplements": ["..."],
 "notes": "..."}"""

VERIFY_PROMPT = """You verify an analysis of an Ancient Greek (possibly fragmentary) text.

Rules:
1. Claims must rely on the ATTACHED SOURCE only; quote exact Greek
   substrings (with diacritics, NFC) as evidence.
2. Text inside a lacuna "[...]" cannot support any claim: mark such
   claims "unverifiable_due_to_missing_data" — NOT "contradicted".
3. Bracketed letters "[Ἀθῆναι]" are an editorial supplement: treat as
   conjectural, lower the confidence, never as certain original text.
4. Breathing marks and iota subscript are semantically significant —
   do not ignore them when matching quotes.

Return ONLY valid JSON:
{"claims": [{"claim": "...",
 "verdict": "grounded|contradicted|unverifiable_due_to_missing_data",
 "quote": "...", "confidence": 0.0, "reasoning": "..."}]}"""

RECONSTRUCT_PROMPT = """You reconstruct LOST text in an Ancient Greek fragment.
STRICT RULES:

1. NEVER invent content silently. Produce 2-4 ranked hypotheses ONLY
   where the surviving context constrains the gap.
2. If the context does not constrain the gap, return
   status "no_reconstruction_possible" — a valid and preferred answer.
3. Respect editorial marks: "[...]" lost text; "[letters]" editor's
   supplement (do not "confirm" it); "<...>", "{...}", "(...)" per the
   edition's conventions.
4. Each hypothesis needs: text, confidence (0-1), evidence (exact
   surviving-context quote). If max confidence < 0.5, return
   "no_reconstruction_possible".

Return ONLY valid JSON:
{"hypotheses": [{"text": "...", "confidence": 0.0, "evidence": "..."}],
 "status": "ok|no_reconstruction_possible"}"""


class AncientGreekPack(LanguagePack):
    """Пак древнегреческого: маркеры изданий + промпты (без морфологии)."""

    iso_code = "grc"
    display_name = "Ancient Greek"
    period = (-800, 600)
    direction = "ltr"

    special_tokens = {
        "lacuna": ["[...]", "[…]", "[lacuna]", "[---]"],
        "editorial": ["<...>", "<*>"],
        "deletion": ["{...}"],
        "uncertain": ["(...)", "[...?]"],
    }

    prompts = {
        "extract": EXTRACT_PROMPT,
        "verify": VERIFY_PROMPT,
        "reconstruct": RECONSTRUCT_PROMPT,
    }

    unicode_ranges = ((0x0370, 0x03FF), (0x1F00, 0x1FFF))

    def detect_markers(self, text: str) -> List[Marker]:
        """Статические токены + контекстная классификация [ ... ]."""
        markers = self._markers_from_special_tokens(text)
        covered = set()
        for marker in markers:
            covered.update(range(marker.start, marker.end))

        for match in _BRACKET_RE.finditer(text):
            if any(index in covered for index in range(match.start(), match.end())):
                continue  # уже покрыт статическим токеном ([...], [---] и т.п.)
            kind = "lacuna" if _GAP_ONLY_RE.match(match.group(1)) else "supplement"
            markers.append(Marker(
                kind=kind, text=match.group(0),
                start=match.start(), end=match.end(),
            ))

        markers.sort(key=lambda marker: marker.start)
        return markers
