"""
AEON Language Pack — реестр (Фаза 2, шаг 2.0).

Eager-registration + lazy-instantiation (стоп-точка 2.0 №3): регистрируем
фабрику (класс / инстанс / callable с атрибутом iso_code), инстанс пака
создаётся при первом get() и валидируется по контракту.

Только stdlib. Реестр пуст до появления паков (2.1 Ancient Greek / 2.2 Latin):
    from aeon.language import registry
    registry.list_available()   # []
"""

import threading
from typing import Callable, Dict, List, Optional, Union

from .base import LanguagePack
from ..logging_config import get_logger, log_event

_PackSource = Union[LanguagePack, type, Callable[[], LanguagePack]]


class _PackSpec:
    """Ленивая обёртка: фабрика + кешированный инстанс."""

    def __init__(self, source: _PackSource, iso_code: str):
        self.iso_code = iso_code
        if isinstance(source, LanguagePack):
            source.validate()  # fail-fast для готовых инстансов
            self._factory: Optional[Callable[[], LanguagePack]] = None
            self._instance: Optional[LanguagePack] = source
        else:
            self._factory = source
            self._instance = None

    def get(self) -> LanguagePack:
        if self._instance is None:
            self._instance = self._factory()  # type: ignore[misc]
            self._instance.validate()
        return self._instance


_REGISTRY: Dict[str, _PackSpec] = {}
_LOCK = threading.Lock()


def register(pack: _PackSource, *, force: bool = False) -> str:
    """
    Регистрирует языковой пак (инстанс, класс или фабрика с iso_code).

    Returns: iso_code.
    Raises: ValueError — нет iso_code или дубль без force=True.
    """
    if isinstance(pack, LanguagePack):
        iso_code = pack.iso_code
    else:
        iso_code = getattr(pack, "iso_code", None)
    if not iso_code:
        raise ValueError(
            "Не удалось определить iso_code: передайте инстанс/класс LanguagePack "
            "или callable с атрибутом iso_code."
        )

    with _LOCK:
        if iso_code in _REGISTRY and not force:
            raise ValueError(
                f"LanguagePack '{iso_code}' уже зарегистрирован. "
                f"Для осознанного override используйте force=True."
            )
        _REGISTRY[iso_code] = _PackSpec(pack, iso_code)
    return iso_code


def get(iso_code: str) -> LanguagePack:
    """Пак по ISO-коду (ленивая инстанциация + валидация контракта)."""
    with _LOCK:
        spec = _REGISTRY.get(iso_code)
        if spec is None:
            available = ", ".join(sorted(_REGISTRY)) or "нет"
            raise KeyError(
                f"LanguagePack '{iso_code}' не зарегистрирован. Доступные: {available}"
            )
    return spec.get()


def list_available() -> List[str]:
    """Отсортированный список ISO-кодов зарегистрированных паков."""
    with _LOCK:
        return sorted(_REGISTRY)


def detect(text: str) -> Optional[LanguagePack]:
    """
    Эвристическая детекция языка — двухфазно (algorithm, refinement 2.2 №4):
      1) Unicode-ranges: если есть hits — побеждает max-hits (алфавит решает);
         при равенстве кандидатов — фаза 2.
      2) detect_heuristic паков: disambiguation для общего алфавита
         (ASCII-латынь vs английский).
    Если итоговый score <= 0 → None.

    Tie-break: алфавитный iso_code (детерминирован, порядок регистрации
    не влияет); при выборе из нескольких кандидатов логируется
    `detect_ambiguous`.

    Ограничение (стоп-точка 2.0 №2): древний и современный греческий
    по codepoints НЕ различаются — возвращается кандидат ('grc').
    """
    if not text or not text.strip():
        return None

    scores: Dict[str, float] = {
        iso_code: float(_count_unicode_hits(text, get(iso_code).unicode_ranges))
        for iso_code in list_available()
    }
    method = "ranges"
    best = max(scores.values(), default=0.0)
    if best <= 0:
        method = "heuristic"
        scores = {
            iso_code: max(0.0, get(iso_code).detect_heuristic(text))
            for iso_code in scores
        }
        best = max(scores.values(), default=0.0)
    if best <= 0:
        return None

    top = sorted(iso_code for iso_code, score in scores.items() if score == best)
    if len(top) > 1:
        log_event(
            get_logger("aeon.language"),
            "detect_ambiguous",
            candidates=list(top),
            winner=top[0],
            method=method,
            score=best,
        )
    return get(top[0])


def clear() -> None:
    """Сброс реестра (тесты и перезагрузка)."""
    with _LOCK:
        _REGISTRY.clear()


def _count_unicode_hits(text: str, ranges) -> int:
    if not ranges:
        return 0
    return sum(
        1 for char in text
        if any(lo <= ord(char) <= hi for lo, hi in ranges)
    )
