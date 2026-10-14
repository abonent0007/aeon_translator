"""
AEON Latin Pack (шаг 2.2) — латынь (ISO 639-1: la; Classical — Neo-Latin).

Конвенции маркеров (подмножество издательских конвенций):
  lacuna     — физический пропуск: [...] […] [lacuna] [---];
  supplement — восстановление редактором в квадратных скобках С БУКВАМИ:
               [Caesar] (контекстное правило — как в grc);
  editorial  — редакторские пометки <...> <*>;
  deletion   — подлежит удалению {...};
  crux       — locus desperatus: †...† — текст есть, но нечитаем/испорчен
               (стоп-точка 2.2 №2: ОТДЕЛЬНЫЙ kind — lacuna = утрачено
               физически; editorial = добавлено редактором; crux = признано
               испорченным, не то и не другое);
  uncertain  — неопределённое чтение (...) [...?].

Нормализация (стоп-точка 2.2 №1):
  - Unicode NFC;
  - j/v и i/u НЕ сводятся: текст сохраняется как в источнике — издания
    (OCT/Teubner/Loeb) печатают классику с осмысленным u/v-различением;
    свёртка — задача поискового слоя (как ς/σ в grc, Ф3), не пака;
  - макроны (ā ē ī ō ū) СОХРАНЯЮТСЯ — семантичны (долгота/метрика);
  - регистр не трогаем.

Эвристика detect: у латыни общий ASCII-алфавит с английским — пак добавляет
word-эвристику (служебные слова + падежные окончания, порог ≥2):
«Gallia est omnis divisa…» → la, «hello world» → None.

Ограничения: Classical vs Medieval/Neo-Latin не различаем; морфологии нет
(Ф3, LatinBERT/CLTK — интерфейс-хук).
"""

import re
from typing import List

from .base import LanguagePack, Marker

_BRACKET_RE = re.compile(r"\[([^\[\]]*)\]")
_GAP_ONLY_RE = re.compile(r"^[\s\.\-…·]*$")
_CRUX_RE = re.compile(r"†([^†]+)†")
_WORD_RE = re.compile(r"[a-zāēīōū]+")

_LATIN_FUNCTION_WORDS = frozenset({
    "est", "sunt", "esse", "in", "et", "cum", "ad", "de", "non", "per",
    "qui", "quae", "quod", "sed", "ut", "atque", "nec", "neque", "aut",
    "ex", "ab", "post", "ante", "inter", "apud", "sine", "pro", "ob",
})
_LATIN_ENDINGS = ("us", "um", "is", "ae", "am", "em", "o", "ibus", "orum", "arum")

EXTRACT_PROMPT = """You are analyzing a Latin text (possibly fragmentary).
Follow the edition's conventions strictly:

1. Gaps: "[...]", "[…]", "[---]", "[lacuna]" mark LOST text (lacuna).
   Bracketed LETTERS, e.g. "[Caesar]", are an editorial SUPPLEMENT —
   conjectural restoration, never certain original text.
2. Daggers mark a locus desperatus: "†word†" is a CORRUPT passage —
   the text exists but is unreadable; it is NOT a lacuna.
3. "<...>"/"<*>" editorial marks; "{...}" to delete; "(...)" and
   "[...?]" uncertain readings.
4. Never guess or "complete" lost or corrupt text.

Return ONLY valid JSON:
{"is_fragment": bool,
 "lacunae": [{"text": "...", "position_hint": "..."}],
 "supplements": ["..."], "cruces": ["..."], "notes": "..."}"""

VERIFY_PROMPT = """You verify an analysis of a Latin (possibly fragmentary) text.

Rules:
1. Claims must rely on the ATTACHED SOURCE only; quote exact Latin
   substrings (preserve macrons and u/v spelling as printed) as evidence.
2. Text inside a lacuna "[...]" cannot support any claim: mark such
   claims "unverifiable_due_to_missing_data" — NOT "contradicted".
3. Bracketed letters "[Caesar]" are an editorial supplement: conjectural,
   lower the confidence, never certain original text.
4. Daggers "†word†" mark a locus desperatus: the passage is corrupt —
   neither confirm nor refute claims based on it; treat as
   "unverifiable_due_to_missing_data".

Return ONLY valid JSON:
{"claims": [{"claim": "...",
 "verdict": "grounded|contradicted|unverifiable_due_to_missing_data",
 "quote": "...", "confidence": 0.0, "reasoning": "..."}]}"""

RECONSTRUCT_PROMPT = """You reconstruct LOST or CORRUPT text in a Latin fragment.
STRICT RULES:

1. NEVER invent content silently. Produce 2-4 ranked hypotheses ONLY
   where the surviving context constrains the gap.
2. If the context does not constrain the gap, return
   status "no_reconstruction_possible" — a valid and preferred answer.
3. Editorial marks: "[...]" lost text; "[letters]" supplement (do not
   "confirm" it); "<...>", "{...}", "(...)" per edition conventions.
4. Cruces "†word†" (locus desperatus) must NOT be reconstructed from the
   passage alone — only with EXTERNAL testimony; otherwise return
   "no_reconstruction_possible".
5. Each hypothesis: text, confidence (0-1), evidence (exact surviving
   context quote). If max confidence < 0.5, return
   "no_reconstruction_possible".

Return ONLY valid JSON:
{"hypotheses": [{"text": "...", "confidence": 0.0, "evidence": "..."}],
 "status": "ok|no_reconstruction_possible"}"""


class LatinPack(LanguagePack):
    """Пак латыни: маркеры изданий (+cruces) + промпты + ASCII-эвристика."""

    iso_code = "la"
    display_name = "Latin"
    period = (-200, 1800)
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

    unicode_ranges = ((0x0080, 0x00FF), (0x0100, 0x017F), (0x0180, 0x024F))

    def detect_markers(self, text: str) -> List[Marker]:
        """Статические токены + cruces (†…†) + контекстные [ ... ]."""
        markers = self._markers_from_special_tokens(text)
        covered = set()
        for marker in markers:
            covered.update(range(marker.start, marker.end))

        for match in _CRUX_RE.finditer(text):
            if any(index in covered for index in range(match.start(), match.end())):
                continue
            markers.append(Marker(
                kind="crux", text=match.group(0),
                start=match.start(), end=match.end(),
            ))
            covered.update(range(match.start(), match.end()))

        for match in _BRACKET_RE.finditer(text):
            if any(index in covered for index in range(match.start(), match.end())):
                continue
            kind = "lacuna" if _GAP_ONLY_RE.match(match.group(1)) else "supplement"
            markers.append(Marker(
                kind=kind, text=match.group(0),
                start=match.start(), end=match.end(),
            ))

        markers.sort(key=lambda marker: marker.start)
        return markers

    def detect_heuristic(self, text: str) -> float:
        """Word-эвристика: служебные слова (1.0) + падежные окончания (0.5)."""
        words = _WORD_RE.findall(text.lower())
        if len(words) < 2:
            return 0.0
        score = 0.0
        for word in words:
            if word in _LATIN_FUNCTION_WORDS:
                score += 1.0
            elif len(word) > 3 and word.endswith(_LATIN_ENDINGS):
                score += 0.5
        return score if score >= 2.0 else 0.0
