"""JSON-LD экспорт (шаг 3.7): linked-data представление v2 (C: inline @context)."""

import json
from typing import Any, Dict, List

from .common import label_of, provenance

_CONTEXT = {
    "schema": "https://schema.org/",
    "aeon": "https://aeon.local/vocab#",
    "wd": "https://www.wikidata.org/entity/",
    "pleiades": "https://pleiades.stoa.org/places/",
    "tm": "https://www.trismegistos.org/text/",
    "name": "schema:name",
    "sameAs": "schema:sameAs",
    "about": "schema:about",
    "inLanguage": "schema:inLanguage",
    "text": "schema:text",
    "identifier": "schema:identifier",
    "dateCreated": "schema:dateCreated",
}

_ENTITY_TYPES = {"person": "schema:Person", "deity": "schema:Person",
                 "place": "schema:Place", "group": "schema:Organization"}


def _same_as(entity: Dict[str, Any]) -> List[str]:
    external = entity.get("external_ids") or {}
    uris = []
    if external.get("wikidata"):
        value = str(external["wikidata"])
        uris.append(value if value.startswith("http") else f"wd:{value}")
    if external.get("pleiades"):
        value = str(external["pleiades"])
        uris.append(value if value.startswith("http") else f"pleiades:{value}")
    if external.get("trismegistos"):
        value = str(external["trismegistos"])
        uris.append(value if value.startswith("http") else f"tm:{value}")
    return uris


def _entity_node(entity: Dict[str, Any]) -> Dict[str, Any]:
    node: Dict[str, Any] = {
        "@type": _ENTITY_TYPES.get(str(entity.get("type") or "").lower(),
                                   "schema:Thing"),
        "name": entity.get("name", ""),
        "aeon:entityType": entity.get("type", ""),
    }
    if entity.get("role"):
        node["aeon:role"] = entity["role"]
    if entity.get("confidence") is not None:
        node["aeon:confidence"] = entity["confidence"]
    same_as = _same_as(entity)
    if same_as:
        node["sameAs"] = same_as
    return node


def render_jsonld(doc: Dict[str, Any], label: str = "") -> str:
    atom = doc.get("atom") or {}
    source = doc.get("source") or {}
    traces = doc.get("traces") or {}
    prov = provenance(doc)
    cross = traces.get("cross_references")
    refs = []
    if isinstance(cross, dict) and isinstance(cross.get("refs"), list):
        refs = [ref for ref in cross["refs"] if isinstance(ref, dict)
                and ref.get("source") and ref.get("target")]

    payload: Dict[str, Any] = {
        "@context": dict(_CONTEXT),
        "@id": f"urn:aeon:{prov['atom_hash']}",
        "@type": "aeon:Analysis",
        "identifier": prov["atom_hash"],
        "dateCreated": prov["created_at"],
        "about": {
            "@type": "aeon:SourceText",
            "text": source.get("content", ""),
            "inLanguage": source.get("language", ""),
        },
        "aeon:version": prov["aeon_version"],
        "aeon:generator": prov["generator"],
        "aeon:provenance": {
            "content_hash": prov["content_hash"],
            "meaning_hash": prov["meaning_hash"],
            "extractor_contract": prov["extractor_contract"],
        },
        "aeon:label": label_of(doc, label),
        "aeon:isFragment": bool(atom.get("is_fragment")),
    }
    entities = atom.get("entities") or []
    if entities:
        payload["aeon:entities"] = [_entity_node(entity) for entity in entities
                                    if isinstance(entity, dict)]
    if refs:
        payload["aeon:crossReferences"] = [
            {
                "aeon:source": ref["source"],
                "aeon:target": ref["target"],
                "aeon:kind": ref.get("kind", ""),
                "aeon:confidence": ref.get("confidence", ""),
            }
            for ref in refs]
    return json.dumps(payload, ensure_ascii=False, indent=1) + "\n"
