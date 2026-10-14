"""Тесты WikidataClient (aeon/entity_linking.py) — mock-HTTP, 0 реальной сети."""

import dataclasses

import pytest

import aeon.entity_linking as el
from aeon.entity_linking import (
    TransportResponse,
    WikidataClient,
    WikidataEntity,
    WikidataTransportError,
    extract_external_ids,
)


SEARCH_HIT = {
    "id": "Q859",
    "title": "Q859",
    "pageid": 1179,
    "concepturi": "http://www.wikidata.org/entity/Q859",
    "label": "Plato",
    "description": "4th-century BCE Greek philosopher",
    "match": {"type": "label", "language": "en", "text": "Plato"},
}

ENTITY_PAYLOAD = {
    "id": "Q859",
    "labels": {
        "en": {"value": "Plato", "language": "en"},
        "ru": {"value": "Платон", "language": "ru"},
    },
    "descriptions": {"en": {"value": "ancient Greek philosopher", "language": "en"}},
    "aliases": {"ru": [{"value": "Платон Афинский"}]},
    "claims": {"P1584": [{"mainsnak": {"datavalue": {"value": "579885"}}}]},
    "sitelinks": {"enwiki": {"title": "Plato"}},
}


class FakeClock:
    """Виртуальное время: sleep продвигает часы (0 реальных пауз)."""

    def __init__(self, start=1000.0):
        self._t = start
        self.slept = []

    def now(self):
        return self._t

    def sleep(self, seconds):
        self.slept.append(seconds)
        self._t += seconds

    def advance(self, seconds):
        self._t += seconds


class FakeTransport:
    """Заменяет HTTP: маршрутизация по action, очереди ответов, инъекция ошибок."""

    def __init__(self, search_payloads=None, entity_payloads=None, errors=None):
        self.search_payloads = list(search_payloads or [])
        self.entity_payloads = list(entity_payloads or [])
        self.errors = list(errors or [])
        self.calls = []

    def __call__(self, url, params, headers, timeout):
        self.calls.append(
            {"url": url, "params": dict(params), "headers": dict(headers), "timeout": timeout}
        )
        if self.errors:
            error = self.errors.pop(0)
            if error is not None:
                raise error
        action = params.get("action")
        if action == "wbsearchentities":
            payload = self.search_payloads.pop(0) if self.search_payloads else {"search": []}
        else:
            payload = self.entity_payloads.pop(0) if self.entity_payloads else {"entities": {}}
        return TransportResponse(status_code=200, data=payload)


def make_client(tmp_path, transport=None, cfg_updates=None, clock=None, **kwargs):
    overrides = {
        "enabled": True,
        "cache_path": str(tmp_path / "wikidata_test.db"),
        "contact_email": "tests@example.com",
    }
    overrides.update(cfg_updates or {})
    cfg = dataclasses.replace(el.CONFIG.entity_linking, **overrides)
    clock = clock or FakeClock()
    client = WikidataClient(
        config=cfg,
        transport=transport or FakeTransport(),
        sleep=clock.sleep,
        clock=clock.now,
        **kwargs,
    )
    return client, clock


def test_search_found(tmp_path):
    transport = FakeTransport(search_payloads=[{"search": [SEARCH_HIT]}])
    client, _ = make_client(tmp_path, transport)

    result = client.search("Plato")

    assert result.source_unavailable is False
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.qid == "Q859"
    assert candidate.label == "Plato"
    assert candidate.match_type == "label"
    assert len(transport.calls) == 1
    assert transport.calls[0]["params"]["action"] == "wbsearchentities"
    client.close()


def test_fetch_details(tmp_path):
    transport = FakeTransport(entity_payloads=[{"entities": {"Q859": ENTITY_PAYLOAD}}])
    client, _ = make_client(tmp_path, transport)

    result = client.get_entity("Q859")

    assert result.source_unavailable is False
    entity = result.entity
    assert entity is not None
    assert entity.qid == "Q859"
    assert entity.label == "Plato"
    assert "Платон Афинский" in entity.aliases
    assert "P1584" in entity.claims
    assert transport.calls[0]["params"]["action"] == "wbgetentities"
    client.close()


def test_cache_hit_zero_network(tmp_path):
    transport = FakeTransport(search_payloads=[{"search": [SEARCH_HIT]}])
    client, _ = make_client(tmp_path, transport)

    first = client.search("Plato")
    second = client.search("Plato")

    assert len(transport.calls) == 1
    assert first.from_cache is False
    assert second.from_cache is True
    assert second.candidates[0].qid == "Q859"
    client.close()


def test_cache_expiry(tmp_path):
    transport = FakeTransport(search_payloads=[{"search": [SEARCH_HIT]}, {"search": [SEARCH_HIT]}])
    client, clock = make_client(tmp_path, transport)

    client.search("Plato")
    clock.advance(7 * 86400 + 1)  # TTL истёк
    result = client.search("Plato")

    assert len(transport.calls) == 2
    assert result.from_cache is False
    client.close()


def test_offline_mode(tmp_path):
    transport = FakeTransport(search_payloads=[{"search": [SEARCH_HIT]}])
    client, _ = make_client(tmp_path, transport, offline=True)

    search = client.search("Plato")
    fetch = client.get_entity("Q859")

    assert transport.calls == []
    assert search.candidates == []
    assert search.reason == "offline_miss"
    assert fetch.entity is None
    assert fetch.source_unavailable is False
    client.close()


def test_rate_limit(tmp_path):
    transport = FakeTransport(search_payloads=[{"search": []} for _ in range(3)])
    client, clock = make_client(tmp_path, transport)

    client.search("one")
    client.search("two")
    client.search("three")

    assert len(clock.slept) == 2  # между 3 запросами — 2 паузы
    assert sum(clock.slept) == pytest.approx(2.0)
    assert all(s == pytest.approx(1.0) for s in clock.slept)
    client.close()


def test_merged_qid_healing_and_mapping_cache(tmp_path):
    entity_payload = {
        "entities": {"Q2": {**ENTITY_PAYLOAD, "id": "Q2"}},
        "redirects": [{"from": "Q1", "to": "Q2"}],
    }
    transport = FakeTransport(entity_payloads=[entity_payload])
    client, _ = make_client(tmp_path, transport)

    first = client.get_entity("Q1")
    assert first.was_redirected is True
    assert first.requested_qid == "Q1"
    assert first.resolved_qid == "Q2"
    assert first.entity is not None
    assert first.entity.qid == "Q2"

    second = client.get_entity("Q1")  # повторно: маппинг из SQLite, 0 HTTP
    assert len(transport.calls) == 1
    assert second.was_redirected is True
    assert second.from_cache is True
    assert second.resolved_qid == "Q2"

    assert client._cache.get_redirect("Q1") == "Q2"
    client.close()


def test_http_redirect_follow(monkeypatch):
    """Транспорт по умолчанию: ручной follow 301 → 302 → 200."""

    class FakeResponse:
        def __init__(self, status, headers=None, data=None):
            self.status_code = status
            self.headers = headers or {}
            self._data = data or {}

        def json(self):
            return self._data

    chain = [
        FakeResponse(301, {"Location": "https://www.wikidata.org/w/api.php?v=2"}),
        FakeResponse(302, {"Location": "https://www.wikidata.org/w/api.php?v=3"}),
        FakeResponse(200, data={"entities": {"Q859": ENTITY_PAYLOAD}}),
    ]
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None, allow_redirects=True):
        calls.append({"url": url, "allow_redirects": allow_redirects})
        return chain.pop(0)

    monkeypatch.setattr(el.requests, "get", fake_get)

    response = el._requests_transport(
        "https://www.wikidata.org/w/api.php", {"action": "wbgetentities"}, {}, 10.0
    )

    assert response.status_code == 200
    assert "entities" in response.data
    assert len(calls) == 3
    assert all(call["allow_redirects"] is False for call in calls)


def test_source_unavailable_after_retries(tmp_path):
    errors = [
        WikidataTransportError("timeout", status_code=408),
        WikidataTransportError("timeout", status_code=408),
        WikidataTransportError("timeout", status_code=408),
    ]
    transport = FakeTransport(errors=errors)
    client, _ = make_client(tmp_path, transport, cfg_updates={"max_attempts": 3})

    result = client.search("Plato")

    assert result.source_unavailable is True
    assert result.candidates == []
    assert len(transport.calls) == 3  # ретраи отработали
    client.close()


def test_transport_5xx_degrades_gracefully(tmp_path):
    errors = [
        WikidataTransportError("HTTP 503", status_code=503),
        WikidataTransportError("HTTP 503", status_code=503),
    ]
    transport = FakeTransport(errors=errors)
    client, _ = make_client(tmp_path, transport, cfg_updates={"max_attempts": 2})

    result = client.get_entity("Q859")

    assert result.source_unavailable is True
    assert result.entity is None
    assert len(transport.calls) == 2
    client.close()


def test_disabled_flag_zero_network(tmp_path):
    transport = FakeTransport(search_payloads=[{"search": [SEARCH_HIT]}])
    client, _ = make_client(tmp_path, transport, enabled=False)

    assert client.search("Plato").candidates == []
    assert client.get_entity("Q859").entity is None
    assert transport.calls == []
    client.close()


def test_user_agent_with_contact(tmp_path):
    transport = FakeTransport(search_payloads=[{"search": []}])
    client, _ = make_client(
        tmp_path, transport, cfg_updates={"contact_email": "research@example.com"}
    )

    client.search("Plato")

    user_agent = transport.calls[0]["headers"]["User-Agent"]
    assert user_agent.startswith("AEON-Translator/4.0")
    assert "research@example.com" in user_agent
    client.close()


def test_missing_entity_reason(tmp_path):
    transport = FakeTransport(
        entity_payloads=[{"entities": {"Q1": {"id": "Q1", "missing": ""}}}]
    )
    client, _ = make_client(tmp_path, transport)

    result = client.get_entity("Q1")

    assert result.entity is None
    assert result.source_unavailable is False
    assert result.reason == "missing"
    client.close()


def test_api_error_payload(tmp_path):
    transport = FakeTransport(
        entity_payloads=[{"error": {"code": "no-such-entity", "info": "..."}}]
    )
    client, _ = make_client(tmp_path, transport)

    result = client.get_entity("Q999")

    assert result.entity is None
    assert result.source_unavailable is False
    assert result.reason == "no-such-entity"
    client.close()


def test_extract_external_ids():
    entity = WikidataEntity(
        qid="Q2",
        claims={
            "P1584": [{"mainsnak": {"datavalue": {"value": "579885"}}}],
            "P11651": [{"mainsnak": {"datavalue": {"value": "12345"}}}],
        },
    )

    ids = extract_external_ids(entity)

    assert ids == {"wikidata": "Q2", "pleiades": "579885", "trismegistos": "12345"}


def test_redirect_mapping_is_permanent(tmp_path):
    """Маппинг merged Q-ID бессрочен: TTL кэша сущностей истёк — маппинг жив."""
    entity_payload = {
        "entities": {"Q2": {**ENTITY_PAYLOAD, "id": "Q2"}},
        "redirects": [{"from": "Q1", "to": "Q2"}],
    }
    transport = FakeTransport(entity_payloads=[entity_payload, entity_payload])
    client, clock = make_client(tmp_path, transport)

    client.get_entity("Q1")
    clock.advance(365 * 86400)  # год спустя: entity-кэш истёк, маппинг — нет
    result = client.get_entity("Q1")

    assert result.was_redirected is True
    assert result.resolved_qid == "Q2"
    assert len(transport.calls) == 2
    # Повторный fetch — уже канонического Q2 (healing из кэша маппинга)
    assert transport.calls[1]["params"]["ids"] == "Q2"
    client.close()


def test_link_mention_end_to_end(tmp_path):
    transport = FakeTransport(
        search_payloads=[{"search": [SEARCH_HIT]}],
        entity_payloads=[{"entities": {"Q859": ENTITY_PAYLOAD}}],
    )
    client, _ = make_client(tmp_path, transport)

    result = client.link_mention("Plato")

    assert result.source_unavailable is False
    assert result.entity is not None
    assert result.entity.qid == "Q859"
    assert result.external_ids == {"wikidata": "Q859", "pleiades": "579885"}
    assert 0.0 < result.score <= 1.0
    assert result.candidates[0].candidate.qid == "Q859"
    client.close()
