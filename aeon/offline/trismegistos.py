"""
AEON Offline — Trismegistos adapter (СТУБ, шаг 2.6).

Реальность: публичного API нет (SSL-цепочка + 403 анти-бот, подтверждено
на шаге 1.2); публичный bulk-датасет не найден (поиск 2.6, стоп-точка №3).
Adapter оставлен как ИНТЕРФЕЙС для будущего датасета (Ф3 backlog):
load() явно отказывает, lookup() → None, в pipeline не включается.
"""

from typing import Any, Dict, Optional

from .base import OfflineAdapter, OfflineDumpError, OfflineRecord

NO_PUBLIC_DATASET = "no_public_dataset"


class TrismegistosOfflineAdapter(OfflineAdapter):
    """Заглушка: только контракт, без данных (Ф3 backlog)."""

    source_name = "trismegistos"

    def __init__(self, db_path: Optional[str] = None, config=None):
        super().__init__(db_path=db_path, config=config)
        self.available = False
        self.reason = NO_PUBLIC_DATASET

    def load(self, path) -> Dict[str, Any]:
        raise OfflineDumpError(
            "no_public_dataset: публичный bulk-датасет Trismegistos не найден"
            " (2.6 стоп-точка №3). Adapter оставлен как интерфейс — Ф3 backlog."
        )

    def lookup(self, key: str) -> Optional[OfflineRecord]:
        return None
