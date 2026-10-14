"""AEON Offline — реестр адаптеров (по образцу language/registry.py)."""

import threading
from typing import Callable, Dict, List, Optional

from .base import OfflineAdapter

_FACTORIES: Dict[str, Callable[..., OfflineAdapter]] = {}
_LOCK = threading.Lock()


def register(adapter_class: Callable[..., OfflineAdapter], *, force: bool = False) -> str:
    """Регистрирует класс адаптера (source_name как ключ)."""
    source_name = getattr(adapter_class, "source_name", None)
    if not source_name or source_name == "base":
        raise ValueError("У адаптера должен быть уникальный source_name")
    with _LOCK:
        if source_name in _FACTORIES and not force:
            raise ValueError(
                f"OfflineAdapter '{source_name}' уже зарегистрирован"
                f" (force=True для override)."
            )
        _FACTORIES[source_name] = adapter_class
    return source_name


def get_adapter(source_name: str, *, db_path: Optional[str] = None,
                config=None) -> OfflineAdapter:
    """Инстанс адаптера (KeyError со списком при отсутствии)."""
    with _LOCK:
        factory = _FACTORIES.get(source_name)
        if factory is None:
            available = ", ".join(sorted(_FACTORIES)) or "нет"
            raise KeyError(
                f"OfflineAdapter '{source_name}' не зарегистрирован."
                f" Доступные: {available}"
            )
    return factory(db_path=db_path, config=config)


def list_adapters() -> List[str]:
    with _LOCK:
        return sorted(_FACTORIES)


def clear() -> None:
    """Сброс реестра (тесты)."""
    with _LOCK:
        _FACTORIES.clear()
