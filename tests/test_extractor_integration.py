"""Интеграция Entity Linking в extractor (шаг 1.2) — mock, 0 сети."""

import dataclasses

import aeon.entity_linking as el
from aeon.crosswalk import PleiadesClient
from aeon.embeddings import EmbeddingEngine
from aeon.entity_linking import TransportResponse, WikidataClient, WikidataTransportError
from aeon.extractor import MeaningExtractor

SEARCH_HIT = {
    "id": "Q8409",
    "label": "Александр Македонский",
    "description": "царь Македонии",
    "match": {"type": "label", "language": "ru", "text": "Александр Македонский"},
}

ENTITY_PAYLOAD = {
    "id": "Q8409",
    "labels": {"ru": {"value": "Александр Македонский"}},
    "descriptions": {"ru": {"value": "царь Македонии"}},
    "aliases": {},
    "claims": {"P1584": [{"mainsnak": {"datavalue": {"value": "550567"}}}]},
    "sitelinks": {},
}

PLEIADES_PAYLOAD = {
    "id": "550567",
    "uri": "https://pleiades.stoa.org/places/550567",
    "title": "Alexandreia",
    "description": "ancient city",
    "placeTypes": [],
    "reprPoint": {"coordinates": [29.9, 40.7]},
}


class FakeTransport:
    """Маршрутизация: Pleiades URL → place; иначе — по action (Wikidata)."""

    def __init__(
        self,
        search_payloads=None,
        entity_payloads=None,
        place_payload=None,
        errors=None,
        place_errors=None,
    ):
        self.search_payloads = list(search_payloads or [])
        self.entity_payloads = list(entity_payloads or [])
        self.place_payload = place_payload
        self.errors = list(errors or [])
        self.place_errors = list(place_errors or [])
        self.calls = []

    def __call__(self, url, params, headers, timeout):
        self.calls.append({"url": url, "params": dict(params)})
        if "pleiades.stoa.org" in url:
            if self.place_errors:
                error = self.place_errors.pop(0)
                if error is not None:
                    raise error
            return TransportResponse(status_code=200, data=self.place_payload or {})
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


def make_cfg(tmp_path, **updates):
    overrides = {
        "enabled": True,
        "contact_email": "tests@example.com",
        "cache_path": str(tmp_path / "wd.db"),
    }
    overrides.update(updates)
    return dataclasses.replace(el.CONFIG.entity_linking, **overrides)


def offline_embeddings():
    engine = EmbeddingEngine()
    engine.available = False  # без загрузки моделей
    return engine


def make_wikidata(tmp_path, transport, **updates):
    return WikidataClient(
        config=make_cfg(tmp_path, **updates),
        transport=transport,
        sleep=lambda _: None,
        clock=lambda: 1000.0,
    )


def make_pleiades(tmp_path, transport, **updates):
    return PleiadesClient(
        config=make_cfg(tmp_path, **updates),
        transport=transport,
        cache_path=str(tmp_path / "crosswalk.db"),
        sleep=lambda _: None,
        clock=lambda: 1000.0,
    )


def test_disabled_entity_linking_zero_network(mock_llm, sample_structure, tmp_path):
    """enabled=False → 0 сетевых вызовов, атомы без external_ids."""
    mock_llm.responses = {"Analyze the following text": sample_structure}
    transport = FakeTransport()
    linker = make_wikidata(tmp_path, transport, enabled=False)
    extractor = MeaningExtractor(
        llm_client=mock_llm,
        embedding_engine=offline_embeddings(),
        entity_linker=linker,
    )

    atom = extractor.extract_from_text("Александр Македонский пошёл на восток.", "russian")

    assert transport.calls == []
    assert atom.entities[0].external_ids == {}
    assert atom.entities[0].link_confidence == 0.0


def test_no_linker_and_config_disabled(mock_llm, sample_structure, monkeypatch):
    """Без linker и при disabled-конфиге linkage не запускается вообще."""
    mock_llm.responses = {"Analyze the following text": sample_structure}
    disabled = dataclasses.replace(
        el.CONFIG,
        entity_linking=dataclasses.replace(el.CONFIG.entity_linking, enabled=False),
    )
    monkeypatch.setattr("aeon.extractor.CONFIG", disabled)

    extractor = MeaningExtractor(
        llm_client=mock_llm, embedding_engine=offline_embeddings()
    )
    atom = extractor.extract_from_text("Александр Македонский.", "russian")

    assert extractor._entity_linker is None
    assert atom.entities[0].external_ids == {}


def test_entity_gets_external_ids(mock_llm, sample_structure, tmp_path):
    """«Александр Македонский» → wikidata Q8409 + pleiades (claims P1584)."""
    mock_llm.responses = {"Analyze the following text": sample_structure}
    transport = FakeTransport(
        search_payloads=[{"search": [SEARCH_HIT]}],
        entity_payloads=[{"entities": {"Q8409": ENTITY_PAYLOAD}}],
    )
    linker = make_wikidata(tmp_path, transport)
    extractor = MeaningExtractor(
        llm_client=mock_llm,
        embedding_engine=offline_embeddings(),
        entity_linker=linker,
    )

    atom = extractor.extract_from_text("Александр Македонский пошёл на восток.", "russian")

    entity = atom.entities[0]
    assert entity.external_ids["wikidata"] == "Q8409"
    assert entity.external_ids["pleiades"] == "550567"
    assert entity.link_confidence > 0.0


def test_pleiades_enrichment_label(mock_llm, sample_structure, tmp_path):
    mock_llm.responses = {"Analyze the following text": sample_structure}
    transport = FakeTransport(
        search_payloads=[{"search": [SEARCH_HIT]}],
        entity_payloads=[{"entities": {"Q8409": ENTITY_PAYLOAD}}],
        place_payload=PLEIADES_PAYLOAD,
    )
    linker = make_wikidata(tmp_path, transport)
    pleiades = make_pleiades(tmp_path, transport)
    extractor = MeaningExtractor(
        llm_client=mock_llm,
        embedding_engine=offline_embeddings(),
        entity_linker=linker,
        pleiades_client=pleiades,
    )

    atom = extractor.extract_from_text("Александр Македонский пошёл на восток.", "russian")

    assert atom.entities[0].external_labels.get("pleiades") == "Alexandreia"
    urls = [call["url"] for call in transport.calls]
    assert any("pleiades.stoa.org/places/550567" in url for url in urls)


def test_pleiades_graceful_degradation(mock_llm, sample_structure, tmp_path):
    """Pleiades недоступен: атом валиден, pleiades-ID от Wikidata остаётся, метки нет."""
    mock_llm.responses = {"Analyze the following text": sample_structure}
    transport = FakeTransport(
        search_payloads=[{"search": [SEARCH_HIT]}],
        entity_payloads=[{"entities": {"Q8409": ENTITY_PAYLOAD}}],
        place_errors=[WikidataTransportError("timeout", status_code=408)] * 2,
    )
    linker = make_wikidata(tmp_path, transport)
    pleiades = make_pleiades(tmp_path, transport, max_attempts=2)
    extractor = MeaningExtractor(
        llm_client=mock_llm,
        embedding_engine=offline_embeddings(),
        entity_linker=linker,
        pleiades_client=pleiades,
    )

    atom = extractor.extract_from_text("Александр Македонский пошёл на восток.", "russian")

    entity = atom.entities[0]
    assert entity.external_ids["wikidata"] == "Q8409"
    assert entity.external_ids["pleiades"] == "550567"  # остаётся из Wikidata
    assert "pleiades" not in entity.external_labels  # обогащение не удалось


def test_fragment_flags_from_completeness(mock_llm, tmp_path):
    structure = {
        "intent": "statement",
        "domain": "general",
        "entities": [],
        "semantic_roles": {},
        "evidence": [],
        "explanation_chain": [],
        "confidence_breakdown": {},
        "complexity": 0.3,
        "urgency": 0.1,
        "extraction_confidence": 0.7,
        "semantic_tokens": [],
    }
    mock_llm.responses = {"Analyze the following text": structure}
    extractor = MeaningExtractor(
        llm_client=mock_llm, embedding_engine=offline_embeddings()
    )

    atom = extractor.extract_from_text("обрывок текста", "russian")

    assert atom.completeness_score == 0.4  # intent + domain из 5 полей
    assert atom.is_fragment is True        # 0.4 < 0.5


def test_fragment_marker_sets_flag_on_atom_and_entities(
    mock_llm, sample_structure
):
    mock_llm.responses = {"Analyze the following text": sample_structure}
    extractor = MeaningExtractor(
        llm_client=mock_llm, embedding_engine=offline_embeddings()
    )

    atom = extractor.extract_from_text("текст [...] с лакуной", "russian")

    assert atom.is_fragment is True
    assert atom.completeness_score == 1.0
    assert atom.entities[0].is_fragment is True  # флаги проброшены на сущности
