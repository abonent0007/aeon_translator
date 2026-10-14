"""Тесты crosswalk (Pleiades + Trismegistos-заглушка) — mock, 0 сети."""

import dataclasses

import aeon.entity_linking as el
from aeon.crosswalk import PleiadesClient, TrismegistosClient
from aeon.entity_linking import TransportResponse, WikidataTransportError

# Структура по документированной схеме Pleiades. Живая проверка из этой сети
# невозможна (сервер не отвечает — см. orchestrator_state.known_deltas);
# парсер защитный (только .get()).
PLEIADES_PAYLOAD = {
    "id": "579885",
    "uri": "https://pleiades.stoa.org/places/579885",
    "title": "Athenae",
    "description": "Athens, Greece",
    "placeTypes": [
        "https://pleiades.stoa.org/vocabularies/place-types/settlement"
    ],
    "reprPoint": {"type": "Point", "coordinates": [23.725, 37.975]},
    "names": [{"attested_form": "Ἀθῆναι", "romanized_form": "Athenai"}],
    "minDate": "-750",
    "maxDate": "2100",
}


class FakeClock:
    def __init__(self, start=1000.0):
        self._t = start
        self.slept = []

    def now(self):
        return self._t

    def sleep(self, seconds):
        self.slept.append(seconds)
        self._t += seconds


class FakeTransport:
    def __init__(self, payload=None, errors=None):
        self.payload = payload
        self.errors = list(errors or [])
        self.calls = []

    def __call__(self, url, params, headers, timeout):
        self.calls.append({"url": url, "headers": dict(headers)})
        if self.errors:
            error = self.errors.pop(0)
            if error is not None:
                raise error
        return TransportResponse(status_code=200, data=self.payload or {})


def make_pleiades(tmp_path, transport, cfg_updates=None, **kwargs):
    overrides = {
        "enabled": True,
        "contact_email": "tests@example.com",
        "cache_path": str(tmp_path / "wd.db"),
    }
    overrides.update(cfg_updates or {})
    cfg = dataclasses.replace(el.CONFIG.entity_linking, **overrides)
    clock = kwargs.pop("clock", None) or FakeClock()
    client = PleiadesClient(
        config=cfg,
        transport=transport,
        cache_path=str(tmp_path / "crosswalk.db"),
        sleep=clock.sleep,
        clock=clock.now,
        **kwargs,
    )
    return client, clock


def test_get_place_success(tmp_path):
    transport = FakeTransport(payload=PLEIADES_PAYLOAD)
    client, _ = make_pleiades(tmp_path, transport)

    result = client.get_place("579885")

    assert result.source_unavailable is False
    place = result.place
    assert place is not None
    assert place.pleiades_id == "579885"
    assert place.title == "Athenae"
    assert place.place_types == ["settlement"]
    assert place.repr_point == [23.725, 37.975]
    assert place.uri.endswith("/places/579885")
    assert transport.calls[0]["url"].endswith("/places/579885/json")
    client.close()


def test_cache_hit_zero_network(tmp_path):
    transport = FakeTransport(payload=PLEIADES_PAYLOAD)
    client, _ = make_pleiades(tmp_path, transport)

    client.get_place("579885")
    second = client.get_place("579885")

    assert len(transport.calls) == 1
    assert second.from_cache is True
    assert second.place is not None
    assert second.place.title == "Athenae"
    client.close()


def test_graceful_degradation_timeout(tmp_path):
    errors = [WikidataTransportError("timeout", status_code=408)] * 3
    transport = FakeTransport(errors=errors)
    client, _ = make_pleiades(tmp_path, transport, cfg_updates={"max_attempts": 3})

    result = client.get_place("579885")

    assert result.place is None
    assert result.source_unavailable is True
    assert len(transport.calls) == 3
    client.close()


def test_disabled_no_network(tmp_path):
    transport = FakeTransport(payload=PLEIADES_PAYLOAD)
    client, _ = make_pleiades(tmp_path, transport, enabled=False)

    result = client.get_place("579885")

    assert transport.calls == []
    assert result.place is None
    assert result.reason == "disabled"
    client.close()


def test_user_agent_contains_contact(tmp_path):
    transport = FakeTransport(payload=PLEIADES_PAYLOAD)
    client, _ = make_pleiades(
        tmp_path, transport, cfg_updates={"contact_email": "research@example.com"}
    )

    client.get_place("579885")

    user_agent = transport.calls[0]["headers"]["User-Agent"]
    assert "research@example.com" in user_agent
    client.close()


def test_trismegistos_stub_never_networks():
    client = TrismegistosClient()

    result = client.get_place("1234")

    assert client.available is False
    assert result.place is None
    assert result.source_unavailable is False
    assert result.reason == "no_public_api"
    client.close()


def test_api_error_payload_returns_reason(tmp_path):
    """Тест-контракт (Wikidata quirk): API-error при HTTP 200 → reason, без исключений."""
    transport = FakeTransport(payload={"error": {"code": "not-found", "info": "..."}})
    client, _ = make_pleiades(tmp_path, transport)

    result = client.get_place("999999")

    assert result.place is None
    assert result.source_unavailable is False
    assert result.reason == "not-found"
    client.close()


def test_offline_adapter_first_chain(tmp_path):
    """Шаг 2.6: offline adapter первый в цепочке → 0 HTTP, source=offline_pleiades."""
    from pathlib import Path as _Path

    from aeon.offline import PleiadesOfflineAdapter

    sample = (_Path(__file__).resolve().parent / "fixtures" / "dumps"
              / "pleiades_sample.jsonl")
    adapter = PleiadesOfflineAdapter(db_path=str(tmp_path / "offline.db"))
    adapter.load(sample)

    transport = FakeTransport(payload=PLEIADES_PAYLOAD)
    client, _ = make_pleiades(tmp_path, transport)
    client.offline_adapter = adapter

    result = client.get_place("579885")

    assert result.place is not None
    assert result.place.source == "offline_pleiades"
    assert result.place.title == "Athenae"
    assert transport.calls == []  # 0 HTTP
    client.close()
    adapter.close()


def test_offline_miss_no_fallback_zero_network(tmp_path, monkeypatch):
    """offline miss + allow_live_fallback=False → 0 сети (offline-only режим)."""
    import dataclasses as _dc
    from pathlib import Path as _Path

    from aeon.config import CONFIG
    from aeon.offline import PleiadesOfflineAdapter

    sample = (_Path(__file__).resolve().parent / "fixtures" / "dumps"
              / "pleiades_sample.jsonl")
    adapter = PleiadesOfflineAdapter(db_path=str(tmp_path / "offline.db"))
    adapter.load(sample)
    monkeypatch.setattr(
        "aeon.crosswalk.CONFIG",
        _dc.replace(CONFIG,
                    offline=_dc.replace(CONFIG.offline, allow_live_fallback=False)),
    )

    transport = FakeTransport(payload=PLEIADES_PAYLOAD)
    client, _ = make_pleiades(tmp_path, transport)
    client.offline_adapter = adapter

    result = client.get_place("999999999")

    assert result.place is None
    assert result.reason == "offline_miss_no_fallback"
    assert transport.calls == []
    client.close()
    adapter.close()
