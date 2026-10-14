"""
AEON Offline Knowledge Adapters (шаг 2.6).

OfflineAdapter — ABC для локальных дампов внешних источников (Pleiades, ...).
SqliteOfflineStore — общая SQLite-механика:
  * атомарная загрузка (BEGIN ... периодические commit ... rollback при ошибке —
    дополнение A: падение в середине не оставляет частичный дамп);
  * индексы создаются ПОСЛЕ загрузки (дополнение B);
  * идемпотентность по dump_version: skip при совпадении, replace при новой
    версии + событие `offline_dump_upgraded` (дополнение C);
  * provenance с license + license_file_sha256 из бандла — доказуемость
    (дополнение E; отсутствие sha256 в meta → OfflineDumpError).

Формат дампа — JSONL (стриминг без внешних парсеров, только stdlib):
  строка 1: {"meta": {"source", "dump_version", "dump_date" (ISO),
                       "license", "license_file_sha256"}}
  далее:    по одной записи на строку.
Спецификация — data/<source>/README.md.
"""

import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..config import CONFIG, OfflineConfig
from ..logging_config import get_logger, log_event
from ..metrics import METRICS

_BATCH_SIZE = 1000


class OfflineDumpError(RuntimeError):
    """Некорректный offline-дамп (meta/license-хэш/битая запись)."""


@dataclass
class OfflineProvenance:
    source_name: str
    dump_version: str = ""
    dump_date: str = ""
    license: str = ""
    license_file_sha256: str = ""
    bundle_size_bytes: int = 0
    loaded_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "dump_version": self.dump_version,
            "dump_date": self.dump_date,
            "license": self.license,
            "license_file_sha256": self.license_file_sha256,
            "bundle_size_bytes": self.bundle_size_bytes,
            "loaded_at": self.loaded_at,
        }


@dataclass
class OfflineRecord:
    id: str
    title: str = ""
    place_types: List[str] = field(default_factory=list)
    repr_point: Optional[List[float]] = None
    uri: str = ""
    source: str = ""
    dump_version: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "place_types": list(self.place_types),
            "repr_point": list(self.repr_point) if self.repr_point else None,
            "uri": self.uri,
            "source": self.source,
            "dump_version": self.dump_version,
        }


def _parse_iso_date(value: str) -> Optional[date]:
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


class SqliteOfflineStore:
    """SQLite-хранилище одного источника: атомарная загрузка + идемпотентность."""

    def __init__(self, db_path: str, source_name: str,
                 logger_name: str = "aeon.offline"):
        self.source_name = source_name
        self._logger = get_logger(logger_name)
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS meta ("
                "source TEXT PRIMARY KEY, dump_version TEXT, dump_date TEXT,"
                "license TEXT, license_file_sha256 TEXT,"
                "bundle_size_bytes INTEGER, loaded_at TEXT)"
            )
            self._conn.commit()

    # ── meta ──

    def meta(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT dump_version, dump_date, license, license_file_sha256,"
                "bundle_size_bytes, loaded_at FROM meta WHERE source=?",
                (self.source_name,),
            ).fetchone()
        if row is None:
            return None
        return {
            "dump_version": row[0], "dump_date": row[1], "license": row[2],
            "license_file_sha256": row[3], "bundle_size_bytes": row[4],
            "loaded_at": row[5],
        }

    def provenance(self) -> Optional[OfflineProvenance]:
        meta = self.meta()
        if meta is None:
            return None
        return OfflineProvenance(source_name=self.source_name, **meta)

    # ── загрузка ──

    def load_jsonl(self, path: Path, table: str, columns_ddl: str,
                   row_builder: Callable[[Dict[str, Any]], Tuple],
                   index_defs: List[str],
                   max_age_days: Optional[int] = None) -> Dict[str, Any]:
        """
        Атомарная загрузка JSONL-дампа.

        Returns: {"status": "loaded"|"skipped", "dump_version", "rows", "dump_date"}.
        Raises: OfflineDumpError (битый дамп / нет license_file_sha256).
        """
        path = Path(path)
        meta_line, record_count = self._read_meta_line(path)
        dump_version = str(meta_line.get("dump_version") or "")
        if not meta_line.get("license_file_sha256"):
            raise OfflineDumpError(
                "meta.license_file_sha256 обязателен (доказательство лицензии,"
                " дополнение E). Укажите SHA256 LICENSE-файла бандла."
            )

        existing = self.meta()
        if existing is not None and existing["dump_version"] == dump_version:
            log_event(self._logger, "offline_dump_skipped",
                      source=self.source_name, dump_version=dump_version)
            return {"status": "skipped", "dump_version": dump_version,
                    "rows": 0, "dump_date": meta_line.get("dump_date", "")}

        replaced = existing is not None and existing["dump_version"] != dump_version
        loaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        bundle_size = path.stat().st_size

        with self._lock:
            self._conn.execute("BEGIN")
        try:
            with self._lock:
                self._conn.execute(f"DROP TABLE IF EXISTS {table}")
                self._conn.execute(f"CREATE TABLE {table} ({columns_ddl})")
            batch: List[Tuple] = []
            processed = 0
            with path.open("r", encoding="utf-8") as handle:
                next(handle)  # meta line уже прочитана
                for lineno, raw_line in enumerate(handle, start=2):
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        item = json.loads(raw_line)
                        batch.append(row_builder(item))
                    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                        raise OfflineDumpError(
                            f"битая запись в строке {lineno}: {exc}"
                        ) from exc
                    if len(batch) >= _BATCH_SIZE:
                        self._insert_batch(table, batch)
                        processed += len(batch)
                        batch = []
            if batch:
                self._insert_batch(table, batch)
                processed += len(batch)
            with self._lock:
                for index_ddl in index_defs:
                    self._conn.execute(index_ddl)
                self._conn.execute(
                    "INSERT OR REPLACE INTO meta (source, dump_version, dump_date,"
                    "license, license_file_sha256, bundle_size_bytes, loaded_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (self.source_name, dump_version,
                     str(meta_line.get("dump_date") or ""),
                     str(meta_line.get("license") or ""),
                     str(meta_line.get("license_file_sha256")),
                     bundle_size, loaded_at),
                )
                self._conn.commit()
        except Exception:
            with self._lock:
                self._conn.rollback()
            raise

        if replaced:
            log_event(self._logger, "offline_dump_upgraded",
                      source=self.source_name,
                      old_version=existing["dump_version"],
                      new_version=dump_version)

        self._check_staleness(meta_line.get("dump_date", ""), max_age_days)
        return {"status": "loaded", "dump_version": dump_version,
                "rows": processed, "dump_date": meta_line.get("dump_date", "")}

    def _read_meta_line(self, path: Path) -> Tuple[Dict[str, Any], int]:
        with path.open("r", encoding="utf-8") as handle:
            first = handle.readline().strip()
        try:
            payload = json.loads(first)
        except json.JSONDecodeError as exc:
            raise OfflineDumpError(f"первая строка дампа не JSON: {exc}") from exc
        meta = payload.get("meta")
        if not isinstance(meta, dict):
            raise OfflineDumpError("первая строка дампа должна содержать {'meta': {...}}")
        if str(meta.get("source") or "") != self.source_name:
            raise OfflineDumpError(
                f"meta.source='{meta.get('source')}' не совпадает с '{self.source_name}'"
            )
        for required in ("dump_version", "dump_date", "license"):
            if not meta.get(required):
                raise OfflineDumpError(f"meta.{required} обязателен")
        return meta, 0

    def _insert_batch(self, table: str, batch: List[Tuple]) -> None:
        placeholders = ",".join("?" for _ in batch[0])
        with self._lock:
            self._conn.executemany(f"INSERT INTO {table} VALUES ({placeholders})", batch)
            self._conn.commit()

    def _check_staleness(self, dump_date: str, max_age_days: Optional[int]) -> None:
        if max_age_days is None:
            max_age_days = CONFIG.offline.max_age_days
        parsed = _parse_iso_date(dump_date)
        if parsed is None:
            return
        age_days = (date.today() - parsed).days
        METRICS.record_offline_dump_age(age_days)
        if age_days > max_age_days:
            log_event(self._logger, "offline_dump_stale",
                      source=self.source_name, dump_date=dump_date,
                      age_days=age_days, max_age_days=max_age_days)

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class OfflineAdapter(ABC):
    """Контракт offline-адаптера (загрузка, lookup, provenance)."""

    source_name: str = "base"

    def __init__(self, db_path: Optional[str] = None, config: Optional[OfflineConfig] = None):
        self.cfg = config or CONFIG.offline
        self._store = SqliteOfflineStore(
            db_path or self.cfg.db_path, self.source_name
        )

    @property
    def loaded(self) -> bool:
        return self._store.meta() is not None

    @abstractmethod
    def load(self, path) -> Dict[str, Any]:
        ...

    @abstractmethod
    def lookup(self, key: str) -> Optional[OfflineRecord]:
        ...

    def provenance(self) -> Optional[OfflineProvenance]:
        return self._store.provenance()

    def dump_age_days(self) -> Optional[int]:
        meta = self._store.meta()
        if meta is None:
            return None
        parsed = _parse_iso_date(meta.get("dump_date", ""))
        return (date.today() - parsed).days if parsed else None

    def close(self) -> None:
        self._store.close()
