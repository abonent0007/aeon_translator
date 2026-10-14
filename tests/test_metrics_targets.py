"""Метрики-цели Фазы 1 (на моках): cache hit-rate > 0.7, вызовов/атом ≤ 5."""

import dataclasses

import aeon.entity_linking as el
from aeon.entity_linking import TransportResponse, WikidataClient
from aeon.metrics import METRICS, reset_metrics

SEARCH_HIT = {
    "id": "Q859",
    "label": "Plato",
    "description": "philosopher",
    "match": {"type": "label", "language": "en", "text": "Plato"},
}

ENTITY_PAYLOAD = {
    "id": "Q859",
    "labels": {"en": {"value": "Plato"}},
    "descriptions": {"en": {"value": "philosopher"}},
    "aliases": {},
    "claims": {},
    "sitelinks": {},
}


class FakeTransport:
    def __init__(self, search_payloads=None, entity_payloads=None):
        self.search_payloads = list(search_payloads or [])
        self.entity_payloads = list(entity_payloads or [])
        self.calls = []

    def __call__(self, url, params, headers, timeout):
        self.calls.append({"params": dict(params)})
        if params.get("action") == "wbsearchentities":
            payload = self.search_payloads.pop(0) if self.search_payloads else {"search": []}
        else:
            payload = self.entity_payloads.pop(0) if self.entity_payloads else {"entities": {}}
        return TransportResponse(status_code=200, data=payload)


def test_metrics_targets_on_warm_cache(tmp_path):
    """Целевые метрики Ф1: hit-rate >0.7 при повторных прогонах, ≤5 внешних вызовов/атом."""
    reset_metrics()
    transport = FakeTransport(
        search_payloads=[{"search": [SEARCH_HIT]}],
        entity_payloads=[{"entities": {"Q859": ENTITY_PAYLOAD}}],
    )
    cfg = dataclasses.replace(
        el.CONFIG.entity_linking,
        enabled=True,
        contact_email="tests@example.com",
        cache_path=str(tmp_path / "metrics.db"),
    )
    client = WikidataClient(
        config=cfg, transport=transport, sleep=lambda _: None, clock=lambda: 1000.0
    )

    METRICS.record_atom()
    with METRICS.timeit("atom"):
        with METRICS.timeit("atom_network"):
            for _ in range(4):  # 1-й прогон — сеть, 3 повторных — тёплый кэш
                client.link_mention("Plato")

    snapshot = METRICS.snapshot()
    assert snapshot["cache_hit_rate"] >= 0.7
    assert snapshot["network_calls_per_atom"] <= 5
    assert snapshot["avg_time_per_atom_network"] is not None
    client.close()
