"""
AEON Offline Knowledge Adapters (шаг 2.6).

Публичный API:
    OfflineAdapter, OfflineRecord, OfflineProvenance, OfflineDumpError
    PleiadesOfflineAdapter / TrismegistosOfflineAdapter (stub)
    get_adapter / register / list_adapters / clear (registry)
"""

from . import registry
from .base import (
    OfflineAdapter,
    OfflineDumpError,
    OfflineProvenance,
    OfflineRecord,
)
from .pleiades import PleiadesOfflineAdapter
from .registry import get_adapter, list_adapters, register
from .trismegistos import TrismegistosOfflineAdapter

registry.register(PleiadesOfflineAdapter)
registry.register(TrismegistosOfflineAdapter)

__all__ = [
    "OfflineAdapter",
    "OfflineRecord",
    "OfflineProvenance",
    "OfflineDumpError",
    "PleiadesOfflineAdapter",
    "TrismegistosOfflineAdapter",
    "registry",
    "register",
    "get_adapter",
    "list_adapters",
]
