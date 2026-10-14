"""
AEON Crosswalk — клиенты специализированных исторических реестров.

PleiadesClient — античная география (`places/<id>/json`). Паттерн тот же, что
у WikidataClient: SQLite-кэш, rate limit, UA, graceful degradation.
ВНИМАНИЕ: схема документальная (живая проверка из dev-сети невозможна —
сервер не отвечает; см. orchestrator_state.known_deltas). Парсер защитный
(только .get()), live-проверка — тест под маркером `network`.

TrismegistosClient — ЗАГЛУШКА (стоп-точка 1.2): публичного API нет
(SSL-мисконфиг сервера + 403 анти-бот на все пути при verify=False).
Интерфейс сохранён для будущей интеграции датасетов (Фаза 2 backlog);
сетевых запросов не выполняет.
"""

import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import CONFIG, EntityLinkingConfig
from .entity_linking import (
    TransportResponse,
    UA_PLAIN,
    UA_TEMPLATE,
    default_transport,
)
from .llm.retries import retry_call
from .logging_config import get_logger, log_event
from .metrics import METRICS

PLEIADES_URL_TEMPLATE = "https://pleiades.stoa.org/places/{pid}/json"


# ═══════════════════════════════════════════════════════════════
# Кэш кросс-уолка (stdlib)
# ═══════════════════════════════════════════════════════════════


class CrosswalkCache:
    """SQLite-кэш кросс-уолка: (kind, key) → payload, TTL."""

    def __init__(
        self,
        path: str,
        ttl_days: float = 30,
        now: Optional[Callable[[], float]] = None,
    ):
        self._now = now or time.time
        self._ttl_sec = float(ttl_days) * 86400.0
        db_path = Path(path)
        if str(db_path) != ":memory:":
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS crosswalk_cache ("
                "kind TEXT NOT NULL, key TEXT NOT NULL, payload TEXT NOT NULL,"
                "fetched_at REAL NOT NULL, PRIMARY KEY (kind, key))"
            )
            self._conn.commit()

    def get(self, kind: str, key: str) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload, fetched_at FROM crosswalk_cache WHERE kind=? AND key=?",
                (kind, key),
            ).fetchone()
        if row and (self._now() - row[1]) < self._ttl_sec:
            return json.loads(row[0])
        return None

    def put(self, kind: str, key: str, payload: dict) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO crosswalk_cache (kind, key, payload, fetched_at) "
                "VALUES (?, ?, ?, ?)",
                (kind, key, json.dumps(payload, ensure_ascii=False), self._now()),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


# ═══════════════════════════════════════════════════════════════
# Результаты
# ═══════════════════════════════════════════════════════════════


@dataclass
class PlaceInfo:
    """Место из Pleiades."""

    pleiades_id: str
    title: str = ""
    description: str = ""
    place_types: List[str] = field(default_factory=list)
    repr_point: Optional[List[float]] = None  # [lon, lat]
    uri: str = ""
    source: str = "live"                      # "live" | "offline_<source>" (шаг 2.6)


@dataclass
class PlaceFetchResult:
    """Результат получения места (паттерн source_unavailable)."""

    place: Optional[PlaceInfo] = None
    source_unavailable: bool = False
    from_cache: bool = False
    reason: str = ""


# ═══════════════════════════════════════════════════════════════
# Pleiades
# ═══════════════════════════════════════════════════════════════


class PleiadesClient:
    """Клиент Pleiades (античная география): кэш, rate limit, деградация."""

    def __init__(
        self,
        config: Optional[EntityLinkingConfig] = None,
        *,
        enabled: Optional[bool] = None,
        offline: Optional[bool] = None,
        cache_path: Optional[str] = None,
        transport: Optional[Callable[..., TransportResponse]] = None,
        sleep: Optional[Callable[[float], None]] = None,
        clock: Optional[Callable[[], float]] = None,
    ):
        self.cfg = config or CONFIG.entity_linking
        self.enabled = self.cfg.enabled if enabled is None else enabled
        self.offline = self.cfg.offline if offline is None else offline
        contact = self.cfg.contact_email
        self.user_agent = UA_TEMPLATE.format(contact=contact) if contact else UA_PLAIN
        self._transport = transport or default_transport
        self._sleep = sleep or time.sleep
        self._clock = clock or time.time
        self._logger = get_logger("aeon.crosswalk")
        self._rate_lock = threading.Lock()
        self._last_request_at: Optional[float] = None

        if cache_path is None:
            base = Path(self.cfg.cache_path)
            cache_path = str(base.parent / "crosswalk.db")
        self._cache = CrosswalkCache(cache_path, ttl_days=30, now=self._clock)
        self.offline_adapter = None  # шаг 2.6: offline-first цепочка (назначается извне)

    def get_place(self, pleiades_id: str) -> PlaceFetchResult:
        """Место по Pleiades ID (кэш → сеть). Деградация без исключений."""
        if not self.enabled:
            return PlaceFetchResult(reason="disabled")
        if not pleiades_id:
            return PlaceFetchResult(reason="empty_id")

        # Офлайн-цепочка (шаг 2.6): offline adapter → live (если разрешён)
        adapter = getattr(self, "offline_adapter", None)
        if adapter is not None and adapter.loaded:
            record = adapter.lookup(str(pleiades_id))
            if record is not None:
                cached_live = self._cache.get("pleiades", str(pleiades_id))
                if cached_live is not None:
                    log_event(
                        self._logger, "offline_live_conflict",
                        pleiades_id=str(pleiades_id),
                        offline_title=record.title,
                        live_title=str(cached_live.get("title") or ""),
                    )
                return PlaceFetchResult(place=PlaceInfo(
                    pleiades_id=record.id, title=record.title,
                    place_types=list(record.place_types),
                    repr_point=record.repr_point, uri=record.uri,
                    source=f"offline_{adapter.source_name}",
                ))
            fallback_allowed = getattr(
                getattr(CONFIG, "offline", None), "allow_live_fallback", True
            )
            if not fallback_allowed:
                return PlaceFetchResult(reason="offline_miss_no_fallback")

        cached = self._cache.get("pleiades", str(pleiades_id))
        if cached is not None:
            METRICS.record_cache(hit=True)
            return PlaceFetchResult(
                place=self._parse_place(pleiades_id, cached), from_cache=True
            )
        METRICS.record_cache(hit=False)

        if self.offline:
            return PlaceFetchResult(reason="offline_miss")

        url = PLEIADES_URL_TEMPLATE.format(pid=pleiades_id)
        payload = self._api_get(url)
        if payload is None:
            return PlaceFetchResult(source_unavailable=True, reason="source_unavailable")
        if "error" in payload:
            error = payload.get("error") or {}
            return PlaceFetchResult(reason=str(error.get("code", "api_error")))

        self._cache.put("pleiades", str(pleiades_id), payload)
        return PlaceFetchResult(place=self._parse_place(pleiades_id, payload))

    def close(self) -> None:
        self._cache.close()

    # ── внутреннее ──

    def _enforce_rate_limit(self) -> None:
        with self._rate_lock:
            now = self._clock()
            if self._last_request_at is not None:
                wait = self.cfg.rate_limit_sec - (now - self._last_request_at)
                if wait > 0:
                    self._sleep(wait)
                    now = self._clock()
            self._last_request_at = now

    def _api_get(self, url: str) -> Optional[Dict[str, Any]]:
        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}

        def attempt() -> TransportResponse:
            self._enforce_rate_limit()
            METRICS.record_network_call()
            return self._transport(url, {}, headers, self.cfg.timeout_sec)

        try:
            response, _attempts, _delays = retry_call(
                attempt, max_attempts=self.cfg.max_attempts, sleep=self._sleep
            )
        except Exception as exc:
            log_event(self._logger, "pleiades_unavailable", error=str(exc)[:200], url=url)
            return None

        data = response.data
        if not isinstance(data, dict):
            log_event(self._logger, "pleiades_unavailable", error="non-dict payload", url=url)
            return None
        return data

    @staticmethod
    def _parse_place(pleiades_id: str, payload: dict) -> PlaceInfo:
        """Защитный парсер (схема документированная; все поля — через .get)."""
        place_types: List[str] = []
        for place_type in payload.get("placeTypes") or []:
            if isinstance(place_type, str) and place_type:
                place_types.append(place_type.rsplit("/", 1)[-1])

        repr_point: Optional[List[float]] = None
        raw_point = payload.get("reprPoint")
        coordinates: Any = None
        if isinstance(raw_point, dict):
            coordinates = raw_point.get("coordinates")
        elif isinstance(raw_point, (list, tuple)):
            coordinates = raw_point
        if isinstance(coordinates, (list, tuple)) and len(coordinates) == 2:
            try:
                repr_point = [float(coordinates[0]), float(coordinates[1])]
            except (TypeError, ValueError):
                repr_point = None

        return PlaceInfo(
            pleiades_id=str(payload.get("id") or pleiades_id),
            title=str(payload.get("title") or ""),
            description=str(payload.get("description") or ""),
            place_types=place_types,
            repr_point=repr_point,
            uri=str(payload.get("uri") or ""),
        )


# ═══════════════════════════════════════════════════════════════
# Trismegistos (заглушка — стоп-точка 1.2)
# ═══════════════════════════════════════════════════════════════


class TrismegistosClient:
    """
    Заглушка Trismegistos.

    Факты живой проверки 2026-10-14:
      - https://www.trismegistos.org/ — SSL: unable to get local issuer
        certificate (неполная цепочка сертификатов);
      - при verify=False все пути (/api/, /dataservices/, /tm/…) → HTTP 403
        (анти-бот защита).
    Публичного API нет; интеграция возможна только через датасеты — Фаза 2.
    """

    NO_PUBLIC_API = "no_public_api"

    def __init__(self, config: Optional[EntityLinkingConfig] = None, **kwargs):
        self.cfg = config or CONFIG.entity_linking
        self.enabled = False
        self.available = False
        self.reason = self.NO_PUBLIC_API

    def get_place(self, tm_id: str) -> PlaceFetchResult:
        """Всегда no_public_api; сетевых запросов не выполняет."""
        return PlaceFetchResult(reason=self.NO_PUBLIC_API)

    def close(self) -> None:
        pass
