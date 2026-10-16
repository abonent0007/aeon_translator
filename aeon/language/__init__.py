"""
AEON Language Pack Infrastructure (Фаза 2, шаг 2.0).

Публичный API:
    LanguagePack, Marker   — контракт пака (aeon/language/base.py)
    registry               — реестр (register/get/list_available/detect/clear)
"""

from . import registry
from .base import LanguagePack, Marker
from .registry import detect, get, list_available, register

# Builtin-паки: регистрация классов (инстанциация — ленивая, при первом get)
from . import grc as _grc  # noqa: E402
from . import la as _la  # noqa: E402


def register_builtins() -> None:
    """Перерегистрация builtin-паков (force): восстановление после
    registry.clear() в тестах — иначе паки «теряются» для последующих тестов."""
    registry.register(_grc.AncientGreekPack, force=True)
    registry.register(_la.LatinPack, force=True)


register_builtins()

__all__ = [
    "LanguagePack",
    "Marker",
    "registry",
    "register",
    "register_builtins",
    "get",
    "list_available",
    "detect",
]
