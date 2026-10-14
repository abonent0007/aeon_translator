"""
AEON Language Pack — базовый контракт (Фаза 2, шаг 2.0).

LanguagePack — ABC: метаданные языка/периода, special tokens (лакуны/
редакторские пометки), промпты, пути к словарям и декларативные
Unicode-диапазоны для detect(). Паки регистрируются в registry и
инстанцируются лениво.

Приоритет маркеров (стоп-точка 2.0 №1): если пак задан — его
special_tokens приоритетный источник; semantic_atom.LACUNA_MARKERS —
fallback для вызовов без пака (интеграция в extractor — шаг 2.1+).
"""

import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Union


@dataclass(frozen=True)
class Marker:
    """Найденный в тексте маркер (лакуна/редакторская пометка/...)."""

    kind: str   # "lacuna" | "editorial" | ...
    text: str   # сам токен, например "[...]"
    start: int  # позиция в тексте
    end: int


class LanguagePack(ABC):
    """Контракт языкового пака (метаданные + маркеры + промпты)."""

    # ── обязательные метаданные (переопределяются подклассами) ──
    iso_code: str = ""
    display_name: str = ""
    period: Tuple[int, int] = (0, 0)    # (min_year, max_year); BCE — отрицательные
    direction: str = "ltr"              # "ltr" | "rtl"

    # ── контент пака ──
    # special_tokens: значение — строка или список вариантов
    # (например, lacuna: ["[...]", "…", "[lacuna]"]).
    special_tokens: Dict[str, Union[str, List[str]]] = {}
    prompts: Dict[str, str] = {}          # {"extract", "verify", "reconstruct"}
    dictionaries: Tuple[Path, ...] = ()   # опциональные wordlists

    # ── detect(): декларативные Unicode-диапазоны (lo, hi) ──
    unicode_ranges: Tuple[Tuple[int, int], ...] = ()

    #: Ключи, обязательные в special_tokens / prompts.
    REQUIRED_SPECIAL_TOKENS: Tuple[str, ...] = ("lacuna", "editorial")
    REQUIRED_PROMPTS: Tuple[str, ...] = ("extract", "verify", "reconstruct")

    # ── контракт ──

    @abstractmethod
    def detect_markers(self, text: str) -> List[Marker]:
        """Находит маркеры пака в тексте (реализация — на паке)."""

    def normalize(self, text: str) -> str:
        """Нормализация текста (по умолчанию — Unicode NFC)."""
        return unicodedata.normalize("NFC", text)

    def is_fragment(self, text: str) -> bool:
        """True, если в источнике есть маркеры-лакуны (свойство ИСТОЧНИКА)."""
        return bool(self.detect_markers(text))

    def validate(self) -> None:
        """Проверка контракта пака (fail-fast при регистрации/get)."""
        problems: List[str] = []
        if not self.iso_code:
            problems.append("iso_code пуст")
        missing_tokens = [
            key for key in self.REQUIRED_SPECIAL_TOKENS
            if key not in (self.special_tokens or {})
        ]
        if missing_tokens:
            problems.append(f"special_tokens: нет ключей {missing_tokens}")
        missing_prompts = [
            key for key in self.REQUIRED_PROMPTS
            if key not in (self.prompts or {})
        ]
        if missing_prompts:
            problems.append(f"prompts: нет ключей {missing_prompts}")
        if problems:
            raise ValueError(
                f"LanguagePack '{self.iso_code}' нарушает контракт: "
                + "; ".join(problems)
            )

    # ── helper для паков ──

    def _markers_from_special_tokens(self, text: str) -> List[Marker]:
        """Стандартный поиск маркеров по special_tokens (для подклассов).

        Значение special_tokens: строка ИЛИ список строк — издательские
        конвенции часто содержат несколько вариантов одного маркера
        (например, lacuna: ["[...]", "…", "[lacuna]"]).
        """
        markers: List[Marker] = []
        for kind, tokens in (self.special_tokens or {}).items():
            token_list = [tokens] if isinstance(tokens, str) else list(tokens or [])
            for token in token_list:
                if not token:
                    continue
                start = text.find(token)
                while start != -1:
                    markers.append(Marker(
                        kind=kind, text=token, start=start, end=start + len(token),
                    ))
                    start = text.find(token, start + 1)
        markers.sort(key=lambda marker: marker.start)
        return markers
