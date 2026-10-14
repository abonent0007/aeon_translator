"""
AEON Language Pack Infrastructure (Фаза 2, шаг 2.0).

Публичный API:
    LanguagePack, Marker   — контракт пака (aeon/language/base.py)
    registry               — реестр (register/get/list_available/detect/clear)
"""

from . import registry
from .base import LanguagePack, Marker
from .registry import detect, get, list_available, register

__all__ = [
    "LanguagePack",
    "Marker",
    "registry",
    "register",
    "get",
    "list_available",
    "detect",
]
