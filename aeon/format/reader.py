"""
AEON format — reader v2 + миграция v1 (шаг 3.1).

D2 (правило миграции meaning_hash): v1-`meaning_hash` сохраняется ТОЛЬКО в
`extensions.legacy_v1_original`; новые `content_hash`/`atom_hash`
ВЫЧИСЛЯЮТСЯ ЗАНОВО (не мапим без знания семантики v1 — не угадываем).
"""

import json
from pathlib import Path
from typing import Any, Dict

from ..logging_config import get_logger, log_event
from .validator import AeonSchemaError, update_extensions, validate_v2
from .versioning import compatibility
from .writer import TRACE_SLOTS, compute_atom_hash, compute_content_hash

_V1_ENTITY_DEFAULTS = {
    "external_ids": {},
    "external_labels": {},
    "link_confidence": 0.0,
    "source_unavailable": False,
    "is_fragment": False,
    "completeness_score": 1.0,
}


def load_v2(path) -> Dict[str, Any]:
    """Чтение v2-документа; валидация обязательна."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        compatibility(str(doc.get("aeon_version", "")))
    except Exception as exc:
        raise AeonSchemaError(str(exc)) from exc
    validate_v2(doc)
    _normalize_contract_metadata(doc)
    return doc


def _normalize_contract_metadata(doc: Dict[str, Any]) -> None:
    """2b: старые v2-файлы (до extractor-contract v1) получают маркер legacy.

    Правило куратора: существующие v2 (2.7.x) не переписываются, но при
    загрузке chain-семантика маркируется `v3.0-legacy` (могла содержать
    инструкции, а не semantic claims) + событие для аудита.
    """
    meta = doc.get("metadata") or {}
    if "extractor_contract" not in meta:
        meta["extractor_contract"] = "v3.0-legacy"
        meta.setdefault("chain_language", "en")
        meta.setdefault("anchor_language", None)
        doc["metadata"] = meta
        log_event(
            get_logger("aeon.format"),
            "v2_legacy_contract_defaulted",
            note="old v2 (pre extractor-contract v1): chain may contain "
                 "instructions, not semantic claims",
        )


def load_v1_and_migrate(path) -> Dict[str, Any]:
    """Чтение v1-файла (production v1 reader) → v2-документ в памяти."""
    from ..aeon_format import AeonFormat

    atoms = AeonFormat.deserialize(str(path))
    if not atoms:
        raise AeonSchemaError("v1-файл не содержит атомов")
    atom = atoms[0]

    source_content = getattr(atom, "source_text", "") or ""
    entities = [
        {**{"name": getattr(e, "name", ""), "type": getattr(e, "type", "concept"),
            "role": getattr(e, "role", ""), "span": getattr(e, "span", ""),
            "confidence": getattr(e, "confidence", 1.0)}, **_V1_ENTITY_DEFAULTS}
        for e in getattr(atom, "entities", [])
    ]

    core = {
        "content_hash": compute_content_hash(source_content),
        "atom_hash": compute_atom_hash(atom),
        "meaning_hash": getattr(atom, "meaning_hash", ""),
        "text": source_content,
        "intent": getattr(atom, "intent", ""),
        "domain": getattr(atom, "domain", ""),
        "entities": entities,
        "semantic_roles": dict(getattr(atom, "semantic_roles", {}) or {}),
        "primitive_coordinates": list(getattr(atom, "primitive_coordinates", []) or []),
        "complexity": getattr(atom, "complexity", 0.0),
        "urgency": getattr(atom, "urgency", 0.0),
        "explanation_chain": list(getattr(atom, "explanation_chain", []) or []),
        "evidence": list(getattr(atom, "evidence", []) or []),
        "confidence_breakdown": dict(getattr(atom, "confidence_breakdown", {}) or {}),
        "language_origin": getattr(atom, "language_origin", ""),
    }

    doc: Dict[str, Any] = {
        "aeon_version": "2.0.0",
        "created_at": "1970-01-01T00:00:00+00:00",  # v1 не хранил время
        "generator": "aeon-4.0/v1-migration",
        "source": {"content": source_content, "form": "text",
                   "language": getattr(atom, "language_origin", "") or "unknown",
                   "normalized": None},
        "atom": core,
        "traces": {slot: None for slot in TRACE_SLOTS},
        "metadata": {
            "thresholds_snapshot": {
                "legacy": "v1_unknown",
                "note": "пороги v1-прогона не сохранялись; не угадываем",
            },
            "mock": True,  # v1-прогоны: legacy/mock-эпоха
            "pipeline": {
                "steps_requested": ["extract_v1_legacy"],
                "steps_executed": ["extract_v1_legacy"],
                "steps_halted": [],
                "steps_failed": [],
            },
            "llm_provider": None,
            "llm_model": None,
            "chain_language": "en",
            "anchor_language": None,
            "extractor_contract": "v3.0-legacy",
        },
        "extensions": {},
    }

    legacy_original = {
        "meaning_hash": getattr(atom, "meaning_hash", ""),
        "source_text": source_content,
        "intent": core["intent"],
        "domain": core["domain"],
        "entities": entities,
    }
    update_extensions(doc, {"legacy_v1_original": legacy_original})
    validate_v2(doc)
    return doc
