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
    Эвристическая детекция языка: Unicode-hits (unicode_ranges) +
    опциональный бонус пака detect_heuristic (общий алфавит, напр. ASCII-латынь).

    Tie-break (refinement 2.0 №1): обход в алфавитном порядке iso_code —
    при равных score побеждает лексикографически первый (детерминировано,
    порядок регистрации не влияет); неоднозначность логируется событием
    `detect_ambiguous`.

    Ограничение (стоп-точка 2.0 №2): древний и современный греческий
    по codepoints НЕ различаются — возвращается кандидат ('grc');
    точное определение — задача пака (диакритика/морфология, 2.1+).
    """
    if not text or not text.strip():
        return None
    best_pack: Optional[LanguagePack] = None
    best_score = 0.0
    tied: List[str] = []
    for iso_code in list_available():  # sorted ⇒ детерминированный tie-break
        pack = get(iso_code)
        score = _count_unicode_hits(text, pack.unicode_ranges)
        score += max(0.0, pack.detect_heuristic(text))
        if score > best_score:
            best_pack, best_score, tied = pack, score, [iso_code]
        elif score == best_score and score > 0:
            tied.append(iso_code)
    if len(tied) > 1:
        log_event(
            get_logger("aeon.language"),
            "detect_ambiguous",
            candidates=list(tied),
            winner=tied[0],
            hits=best_score,
        )
    return best_pack


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
