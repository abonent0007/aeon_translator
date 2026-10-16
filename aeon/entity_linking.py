"""
AEON Entity Linking — WikidataClient (2-ярусный доступ к Wikidata) + скоринг.

Ярусы:
  1. wbsearchentities — поиск кандидатов (Q-ID) по упоминанию;
  2. wbgetentities   — данные сущности (labels/descriptions/aliases/claims/
     sitelinks) + обработка merged/redirected Q-ID.

Скоринг (шаг 1.2): при нескольких кандидатах — ранжирование по
score_candidate() ∈ [0,1] (тип матча, точность, язык, наличие описания);
link_mention() — сквозной путь: поиск → скоринг → fetch → external_ids.

Инфраструктура:
  - SQLite-кэш (stdlib sqlite3): поиски (query,lang) и сущности (qid), TTL 7 дней;
    маппинг merged Q-ID old→new — БЕССРОЧНЫЙ (слияние — исторический факт);
  - rate limit ≤1 req/sec (threading.Lock + инъектируемые clock/sleep);
  - ретраи на timeout/5xx (прочие 4xx — fail fast), механизм из aeon.llm.retries;
  - offline-режим: только кэш, 0 сетевых вызовов;
  - graceful degradation: недоступность → source_unavailable=True, без исключений;
  - метрики: METRICS.record_network_call / record_cache(main|redirect);
  - JSON-lines события: wikidata_unavailable / wikidata_redirect_healed.

Схема ответов проверена живым запросом 2026-10-14:
  wbsearchentities hit: {id, label, description, match{type,language,text}};
  wbgetentities: {entities: {...}, success: 1}; merged Q-ID → redirects;
  ошибка API: HTTP 200 + {"error": {"code": "no-such-entity", ...}} (known quirk).
"""

import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urljoin

import requests

from .config import CONFIG, EntityLinkingConfig
from .llm.retries import retry_call
from .logging_config import get_logger, log_event
from .metrics import METRICS

API_URL = os.getenv("AEON_WIKIDATA_API_URL",
                    "https://www.wikidata.org/w/api.php")
UA_TEMPLATE = "AEON-Translator/4.0 (research; contact: {contact})"
UA_PLAIN = "AEON-Translator/4.0 (research)"
_HTTP_REDIRECTS = {301, 302, 303, 307, 308}
_MAX_HTTP_REDIRECTS = 5


class WikidataTransportError(Exception):
    """Транспортная ошибка Wikidata (timeout / HTTP >= 400)."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class TransportResponse:
    """Ответ транспорта: HTTP-статус + распарсенный JSON + заголовки."""

    status_code: int
    data: Dict[str, Any]
    headers: Dict[str, str] = field(default_factory=dict)


def _requests_transport(
    url: str, params: Dict[str, Any], headers: Dict[str, str], timeout: float
) -> TransportResponse:
    """Транспорт по умолчанию: requests + ручной follow HTTP-редиректов (≤5)."""
    current_url = url
    current_params: Optional[Dict[str, Any]] = params
    response = None

    for _hop in range(_MAX_HTTP_REDIRECTS):
        try:
            response = requests.get(
                current_url,
                params=current_params,
                headers=headers,
                timeout=timeout,
                allow_redirects=False,
            )
        except requests.Timeout as exc:
            raise WikidataTransportError(f"timeout: {exc}", status_code=408) from exc
        except requests.ConnectionError as exc:
            raise WikidataTransportError(f"connection: {exc}", status_code=408) from exc

        if response.status_code in _HTTP_REDIRECTS:
            location = response.headers.get("Location") or response.headers.get("location")
            if not location:
                break
            current_url = urljoin(current_url, location)
            current_params = None
            continue
        break

    if response is None:  # pragma: no cover - защитная ветка
        raise WikidataTransportError("no response")

    if response.status_code >= 400:
        raise WikidataTransportError(
            f"HTTP {response.status_code}", status_code=response.status_code
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise WikidataTransportError(f"invalid JSON: {exc}") from exc

    return TransportResponse(
        status_code=response.status_code,
        data=data,
        headers=dict(getattr(response, "headers", {}) or {}),
    )


# Публичный алиас для других клиентов (crosswalk: Pleiades, Trismegistos)
default_transport = _requests_transport


# ═══════════════════════════════════════════════════════════════
# SQLite-кэш (stdlib, без ORM)
# ═══════════════════════════════════════════════════════════════


class WikidataCache:
    """SQLite-кэш: поиски, сущности, маппинг merged Q-ID."""

    def __init__(
        self,
        path: str,
        ttl_days: float = 7,
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
                "CREATE TABLE IF NOT EXISTS search_cache ("
                "query TEXT NOT NULL, language TEXT NOT NULL, payload TEXT NOT NULL,"
                "fetched_at REAL NOT NULL, PRIMARY KEY (query, language))"
            )
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS entity_cache ("
                "qid TEXT NOT NULL PRIMARY KEY, payload TEXT NOT NULL, fetched_at REAL NOT NULL)"
            )
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS qid_redirects ("
                "old_qid TEXT NOT NULL PRIMARY KEY, new_qid TEXT NOT NULL, updated_at REAL NOT NULL)"
            )
            self._conn.commit()

    def _fresh(self, fetched_at: float) -> bool:
        return (self._now() - fetched_at) < self._ttl_sec

    def get_search(self, query: str, language: str) -> Optional[List[dict]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload, fetched_at FROM search_cache WHERE query=? AND language=?",
                (query, language),
            ).fetchone()
        if row and self._fresh(row[1]):
            return json.loads(row[0])
        return None

    def put_search(self, query: str, language: str, payload: List[dict]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO search_cache (query, language, payload, fetched_at) "
                "VALUES (?, ?, ?, ?)",
                (query, language, json.dumps(payload, ensure_ascii=False), self._now()),
            )
            self._conn.commit()

    def get_entity(self, qid: str) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload, fetched_at FROM entity_cache WHERE qid=?", (qid,)
            ).fetchone()
        if row and self._fresh(row[1]):
            return json.loads(row[0])
        return None

    def put_entity(self, qid: str, payload: dict) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO entity_cache (qid, payload, fetched_at) VALUES (?, ?, ?)",
                (qid, json.dumps(payload, ensure_ascii=False), self._now()),
            )
            self._conn.commit()

    def get_redirect(self, old_qid: str) -> Optional[str]:
        """Маппинг old→new. Без TTL: слияние Q-ID — неизменяемый исторический факт."""
        with self._lock:
            row = self._conn.execute(
                "SELECT new_qid FROM qid_redirects WHERE old_qid=?", (old_qid,)
            ).fetchone()
        return row[0] if row else None

    def put_redirect(self, old_qid: str, new_qid: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO qid_redirects (old_qid, new_qid, updated_at) "
                "VALUES (?, ?, ?)",
                (old_qid, new_qid, self._now()),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


# ═══════════════════════════════════════════════════════════════
# Результаты и сущности
# ═══════════════════════════════════════════════════════════════


@dataclass
class SearchCandidate:
    """Кандидат из wbsearchentities."""

    qid: str
    label: str = ""
    description: str = ""
    match_type: str = ""
    match_language: str = ""
    rank: int = 0


@dataclass
class SearchResult:
    """Результат поиска: кандидаты + признаки деградации."""

    candidates: List[SearchCandidate] = field(default_factory=list)
    source_unavailable: bool = False
    from_cache: bool = False
    reason: str = ""


@dataclass
class ScoredCandidate:
    """Кандидат с оценкой link_confidence ∈ [0,1]."""

    candidate: SearchCandidate
    score: float


@dataclass
class LinkResult:
    """Сквозной результат link_mention: сущность + внешние ID + скор."""

    entity: Optional["WikidataEntity"] = None
    score: float = 0.0
    external_ids: Dict[str, str] = field(default_factory=dict)
    source_unavailable: bool = False
    from_cache: bool = False
    was_redirected: bool = False
    candidates: List[ScoredCandidate] = field(default_factory=list)
    reason: str = ""


@dataclass
class WikidataEntity:
    """Сущность Wikidata (данные из wbgetentities)."""

    qid: str
    label: str = ""
    description: str = ""
    aliases: List[str] = field(default_factory=list)
    claims: Dict[str, Any] = field(default_factory=dict)
    sitelinks: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityFetchResult:
    """Результат получения сущности (+ healing merged Q-ID)."""

    entity: Optional[WikidataEntity] = None
    source_unavailable: bool = False
    from_cache: bool = False
    was_redirected: bool = False
    requested_qid: Optional[str] = None
    resolved_qid: Optional[str] = None
    reason: str = ""


def extract_external_ids(entity: WikidataEntity) -> Dict[str, str]:
    """Внешние ID из claims: wikidata + Pleiades (P1584) + Trismegistos (P11651)."""
    ids: Dict[str, str] = {}
    if entity.qid:
        ids["wikidata"] = entity.qid
    crosswalk = {"P1584": "pleiades", "P11651": "trismegistos"}
    for prop, name in crosswalk.items():
        for claim in entity.claims.get(prop, []) or []:
            value = (claim.get("mainsnak") or {}).get("datavalue", {}).get("value")
            if isinstance(value, str) and value:
                ids[name] = value
                break
    return ids


# ═══════════════════════════════════════════════════════════════
# Скоринг кандидатов (шаг 1.2)
# ═══════════════════════════════════════════════════════════════

#: Дефолтные веса типов совпадений (wbsearchentities match.type).
MATCH_TYPE_WEIGHTS = {
    "label": 1.0,
    "entity": 0.7,
    "alias": 0.55,
    "description": 0.25,
}
_UNKNOWN_MATCH_WEIGHT = 0.4


def scoring_weights_from_config(
    cfg: Optional[EntityLinkingConfig] = None,
) -> Dict[str, float]:
    """Веса комбинации скора из конфига (env AEON_SCORE_WEIGHT_*, overridable)."""
    cfg = cfg or CONFIG.entity_linking
    return {
        "type": cfg.score_weight_type,
        "exactness": cfg.score_weight_exactness,
        "language": cfg.score_weight_language,
        "description": cfg.score_weight_description,
    }


def _normalize(text: Optional[str]) -> str:
    return (text or "").strip().casefold()


def score_candidate(
    candidate: SearchCandidate,
    query: str,
    language: str = "en",
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    Оценка кандидата ∈ [0,1]: монотонна по качеству совпадения.

    Компоненты:
      type        — вес match.type (label > entity > alias > description);
      exactness   — точное совпадение label с запросом > префикс > прочее;
      language    — язык матча совпадает с целевым;
      description — у кандидата есть описание.
    Веса — из CONFIG.entity_linking (env AEON_SCORE_WEIGHT_*), либо явные.
    """
    weights = weights or scoring_weights_from_config()
    type_weight = MATCH_TYPE_WEIGHTS.get(candidate.match_type, _UNKNOWN_MATCH_WEIGHT)

    label = _normalize(candidate.label)
    normalized_query = _normalize(query)
    if label and normalized_query and label == normalized_query:
        exactness = 1.0
    elif label and normalized_query and label.startswith(normalized_query):
        exactness = 0.65
    else:
        exactness = 0.35

    if not candidate.match_language or candidate.match_language == language:
        language_match = 1.0
    else:
        language_match = 0.6

    has_description = 1.0 if candidate.description else 0.5

    score = (
        weights.get("type", 0.40) * type_weight
        + weights.get("exactness", 0.35) * exactness
        + weights.get("language", 0.15) * language_match
        + weights.get("description", 0.10) * has_description
    )
    return round(min(1.0, max(0.0, score)), 4)


def rank_candidates(
    candidates: List[SearchCandidate],
    query: str,
    language: str = "en",
    weights: Optional[Dict[str, float]] = None,
) -> List[ScoredCandidate]:
    """Ранжирование кандидатов по score (desc), тайбрейк — исходный rank API."""
    scored = [
        ScoredCandidate(
            candidate=candidate,
            score=score_candidate(candidate, query, language, weights=weights),
        )
        for candidate in candidates
    ]
    scored.sort(key=lambda item: (-item.score, item.candidate.rank))
    return scored


# ═══════════════════════════════════════════════════════════════
# Клиент
# ═══════════════════════════════════════════════════════════════


class WikidataClient:
    """Клиент Wikidata Action API: кэш, rate limit, healing, деградация."""

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
        self._transport = transport or _requests_transport
        self._sleep = sleep or time.sleep
        self._clock = clock or time.time
        self._logger = get_logger("aeon.entity_linking")
        self._rate_lock = threading.Lock()
        self._last_request_at: Optional[float] = None
        self._cache = WikidataCache(
            cache_path or self.cfg.cache_path,
            ttl_days=self.cfg.cache_ttl_days,
            now=self._clock,
        )

    # ── публичный API ──

    def search(self, mention: str, language: str = "en", limit: int = 5) -> SearchResult:
        """Ярус 1: поиск кандидатов по упоминанию (кэш → сеть)."""
        if not self.enabled:
            return SearchResult(reason="disabled")
        if not mention or not mention.strip():
            return SearchResult(reason="empty_mention")

        cached = self._cache.get_search(mention, language)
        if cached is not None:
            METRICS.record_cache(hit=True)
            return SearchResult(
                candidates=[self._parse_candidate(item, idx) for idx, item in enumerate(cached)],
                from_cache=True,
            )
        METRICS.record_cache(hit=False)

        if self.offline:
            return SearchResult(reason="offline_miss")

        payload = self._api_get({
            "action": "wbsearchentities",
            "search": mention,
            "language": language,
            "uselang": language,
            "limit": limit,
            "type": "item",
            "format": "json",
        })
        if payload is None:
            return SearchResult(source_unavailable=True, reason="source_unavailable")

        raw_hits = payload.get("search") or []
        self._cache.put_search(mention, language, raw_hits)
        return SearchResult(
            candidates=[self._parse_candidate(item, idx) for idx, item in enumerate(raw_hits)]
        )

    def get_entity(self, qid: str, language: str = "en") -> EntityFetchResult:
        """Ярус 2: данные сущности (+ healing merged Q-ID, маппинг в кэше)."""
        if not self.enabled:
            return EntityFetchResult(reason="disabled")
        if not qid:
            return EntityFetchResult(reason="empty_qid")

        requested = qid
        redirect_mapping = self._cache.get_redirect(qid)
        if redirect_mapping:
            METRICS.record_cache(hit=True, namespace="redirect")
        else:
            METRICS.record_cache(hit=False, namespace="redirect")
        canonical = redirect_mapping or qid
        was_redirected = canonical != requested

        cached = self._cache.get_entity(canonical)
        if cached is not None:
            METRICS.record_cache(hit=True)
            return EntityFetchResult(
                entity=self._parse_entity(cached),
                from_cache=True,
                was_redirected=was_redirected,
                requested_qid=requested,
                resolved_qid=canonical,
            )
        METRICS.record_cache(hit=False)

        if self.offline:
            return EntityFetchResult(requested_qid=requested, reason="offline_miss")

        payload = self._api_get({
            "action": "wbgetentities",
            "ids": canonical,
            "props": "labels|descriptions|aliases|claims|sitelinks",
            "languages": language,
            "format": "json",
        })
        if payload is None:
            return EntityFetchResult(
                source_unavailable=True, requested_qid=requested, reason="source_unavailable"
            )

        if "error" in payload:
            error = payload.get("error") or {}
            return EntityFetchResult(
                requested_qid=requested,
                reason=str(error.get("code", "api_error")),
            )

        entities = payload.get("entities") or {}
        redirects = self._parse_redirects(payload.get("redirects"))
        canonical = redirects.get(canonical, canonical)
        was_redirected = canonical != requested
        if was_redirected and redirects:
            for old_qid, new_qid in redirects.items():
                self._cache.put_redirect(old_qid, new_qid)
            log_event(
                self._logger,
                "wikidata_redirect_healed",
                old_qid=requested,
                new_qid=canonical,
            )

        entity_payload = entities.get(canonical) or entities.get(requested)
        if entity_payload is None:
            return EntityFetchResult(requested_qid=requested, reason="no_entity_in_response")

        if "missing" in entity_payload:
            return EntityFetchResult(
                requested_qid=requested, resolved_qid=requested, reason="missing"
            )

        self._cache.put_entity(canonical, entity_payload)
        return EntityFetchResult(
            entity=self._parse_entity(entity_payload),
            was_redirected=was_redirected,
            requested_qid=requested,
            resolved_qid=canonical,
        )

    def link_mention(
        self, mention: str, language: str = "en", limit: int = 5
    ) -> LinkResult:
        """
        Сквозной linking: поиск → скоринг → fetch → external_ids.
        Не бросает исключений; деградация выражается полями результата.
        """
        search_result = self.search(mention, language=language, limit=limit)
        if search_result.source_unavailable:
            return LinkResult(source_unavailable=True, reason="source_unavailable")
        if not search_result.candidates:
            return LinkResult(
                reason=search_result.reason or "no_candidates",
                from_cache=search_result.from_cache,
            )

        scored = rank_candidates(search_result.candidates, mention, language)
        best = scored[0]

        fetch = self.get_entity(best.candidate.qid, language=language)
        if fetch.source_unavailable:
            return LinkResult(
                score=best.score,
                candidates=scored,
                source_unavailable=True,
                reason="source_unavailable",
            )
        if fetch.entity is None:
            return LinkResult(
                score=best.score,
                candidates=scored,
                reason=fetch.reason or "fetch_failed",
            )

        return LinkResult(
            entity=fetch.entity,
            score=best.score,
            external_ids=extract_external_ids(fetch.entity),
            was_redirected=fetch.was_redirected,
            from_cache=search_result.from_cache and fetch.from_cache,
            candidates=scored,
        )

    def close(self) -> None:
        """Закрывает SQLite-соединение."""
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

    def _api_get(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """GET с rate limit + ретраями. None — источник недоступен (не падаем)."""
        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}

        def attempt() -> TransportResponse:
            self._enforce_rate_limit()
            METRICS.record_network_call()
            return self._transport(API_URL, dict(params), headers, self.cfg.timeout_sec)

        try:
            response, _attempts, _delays = retry_call(
                attempt,
                max_attempts=self.cfg.max_attempts,
                sleep=self._sleep,
            )
        except Exception as exc:
            log_event(
                self._logger,
                "wikidata_unavailable",
                error=str(exc)[:200],
                action=params.get("action"),
            )
            return None

        data = response.data
        if not isinstance(data, dict):
            log_event(
                self._logger,
                "wikidata_unavailable",
                error="non-dict payload",
                action=params.get("action"),
            )
            return None
        return data

    @staticmethod
    def _parse_candidate(item: dict, rank: int) -> SearchCandidate:
        match = item.get("match") or {}
        return SearchCandidate(
            qid=item.get("id", ""),
            label=item.get("label", ""),
            description=item.get("description", ""),
            match_type=match.get("type", ""),
            match_language=match.get("language", ""),
            rank=rank,
        )

    @staticmethod
    def _parse_entity(payload: dict) -> WikidataEntity:
        def _first_value(lang_map: dict) -> str:
            for lang in ("en", "ru", *lang_map.keys()):
                if lang in lang_map:
                    return lang_map[lang].get("value", "")
            return ""

        aliases: List[str] = []
        for lang_aliases in (payload.get("aliases") or {}).values():
            for alias in lang_aliases:
                value = alias.get("value")
                if value:
                    aliases.append(value)

        return WikidataEntity(
            qid=payload.get("id", ""),
            label=_first_value(payload.get("labels") or {}),
            description=_first_value(payload.get("descriptions") or {}),
            aliases=aliases,
            claims=payload.get("claims") or {},
            sitelinks=payload.get("sitelinks") or {},
        )

    @staticmethod
    def _parse_redirects(raw: Any) -> Dict[str, str]:
        """merged Q-ID: поддерживает list[{from,to}] и dict{old:new}."""
        result: Dict[str, str] = {}
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get("from") and item.get("to"):
                    result[str(item["from"])] = str(item["to"])
        elif isinstance(raw, dict):
            for old, new in raw.items():
                result[str(old)] = str(new)
        return result
