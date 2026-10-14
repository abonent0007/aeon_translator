"""AEON Offline — Pleiades adapter (шаг 2.6; JSONL-дамп, см. data/pleiades/README.md)."""

import json
from typing import Any, Dict, List, Optional, Tuple

from .base import OfflineAdapter, OfflineRecord

TABLE = "pleiades"
_COLUMNS_DDL = (
    "id TEXT PRIMARY KEY, title TEXT, place_types TEXT,"
    " repr_point TEXT, uri TEXT, dump_version TEXT"
)
_INDEX_DEFS = [
    "CREATE INDEX IF NOT EXISTS idx_pleiades_title ON pleiades(title)",
    "CREATE INDEX IF NOT EXISTS idx_pleiades_place_types ON pleiades(place_types)",
]


class PleiadesOfflineAdapter(OfflineAdapter):
    """Офлайн-справочник Pleiades: lookup(id) → OfflineRecord (без сети)."""

    source_name = "pleiades"

    def load(self, path) -> Dict[str, Any]:
        return self._store.load_jsonl(
            path, TABLE, _COLUMNS_DDL, self._row_builder, _INDEX_DEFS,
        )

    def lookup(self, key: str) -> Optional[OfflineRecord]:
        from ..metrics import METRICS

        row = None
        try:
            with self._store._lock:
                row = self._store._conn.execute(
                    "SELECT id, title, place_types, repr_point, uri, dump_version"
                    " FROM pleiades WHERE id=?", (str(key),),
                ).fetchone()
        except Exception:
            row = None  # таблица отсутствует до загрузки дампа

        if row is None:
            METRICS.record_cache(hit=False, namespace="offline")
            return None
        METRICS.record_cache(hit=True, namespace="offline")
        return OfflineRecord(
            id=row[0], title=row[1] or "",
            place_types=json.loads(row[2]) if row[2] else [],
            repr_point=json.loads(row[3]) if row[3] else None,
            uri=row[4] or "", source=self.source_name, dump_version=row[5] or "",
        )

    @staticmethod
    def _row_builder(item: Dict[str, Any]) -> Tuple:
        place_types: List[str] = list(item.get("place_types") or [])
        repr_point = item.get("repr_point")
        return (
            str(item["id"]),
            str(item.get("title") or ""),
            json.dumps(place_types, ensure_ascii=False),
            json.dumps(repr_point, ensure_ascii=False) if repr_point else None,
            str(item.get("uri") or ""),
            str(item.get("dump_version") or ""),
        )
