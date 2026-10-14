"""
AEON format — writer v2 (шаг 3.1).

Контракты:
  * сохраняются ТОЛЬКО структурированные результаты (parsed JSON), без raw LLM
    (стоп-точка №3); целевой размер полного атома < 200KB;
  * thresholds_snapshot ЧИТАЕТСЯ из атома (зафиксирован при создании, D3) —
    writer НЕ пересчитывает и НЕ подставляет текущий CONFIG;
    атом без snapshot → AeonSchemaError (D4);
  * mock-guard (стоп-точка №2): mock=false без DEEPSEEK_API_KEY запрещён;
    обход только force_unsafe=True + обязательный force_reason, с аудит-логом
    aeon_mock_flag_bypassed (reason/operator/trace_id).
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import CONFIG
from ..logging_config import get_logger, log_event
from .validator import AeonSchemaError, validate_v2

GENERATOR = "aeon-4.0"
TRACE_SLOTS = (
    "extraction", "entity_linking", "verification", "linguistics", "focus",
    "reconstruction", "variant_readings", "morphology", "cross_references",
)
_ATOM_HASH_FIELDS = ("intent", "domain", "semantic_roles", "evidence",
                     "complexity", "urgency", "completeness_score")

_logger = get_logger("aeon.format")


def build_thresholds_snapshot(config=None) -> Dict[str, Any]:
    """Снимок порогов (вызывать на МОМЕНТ создания атома, D3)."""
    full = config or CONFIG
    return {
        "detective": {"min_confidence": full.detective.min_confidence,
                      "require_quote": full.detective.require_quote},
        "expert": {"min_confidence": full.expert.min_confidence,
                   "min_sources": full.expert.min_sources},
        "logician": {"min_coherence": full.logician.min_coherence,
                     "max_contradictions": full.logician.max_contradictions},
        "abstention_threshold": full.abstention_threshold,
        "layers": {"min_confidence": full.linguistics.layer_min_confidence},
        "fragments": {"min_confidence": full.fragments.min_confidence,
                      "density_threshold": full.fragments.density_threshold},
        "legacy": {"risk_verified_max": full.legacy_verification.risk_verified_max},
    }


def compute_content_hash(source_content: str) -> str:
    """Доп. №2: детерминированный хэш входа."""
    return hashlib.sha256((source_content or "").encode("utf-8")).hexdigest()


def compute_atom_hash(atom) -> str:
    """Доп. №2: канонический хэш ядра результата (может отличаться между прогонами)."""
    core = {field: getattr(atom, field, None) for field in _ATOM_HASH_FIELDS}
    canonical = json.dumps(core, ensure_ascii=False, sort_keys=True,
                           default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def dump_v2(atom, *, source: Dict[str, Any], traces: Dict[str, Any],
            metadata: Optional[Dict[str, Any]] = None,
            pipeline: Optional[Dict[str, Any]] = None,
            mock: bool = True, created_at: Optional[str] = None,
            force_unsafe: bool = False,
            force_reason: Optional[str] = None,
            trace_id: Optional[str] = None) -> Dict[str, Any]:
    """Собирает v2-документ (dict), валидирует и возвращает."""
    snapshot = getattr(atom, "thresholds_snapshot", None)
    if not snapshot:
        raise AeonSchemaError(
            "атом без thresholds_snapshot: snapshot фиксируется при СОЗДАНИИ "
            "атома (D3), writer не пересчитывает (D4)"
        )

    if not mock and not os.getenv("DEEPSEEK_API_KEY"):
        if not (force_unsafe and force_reason):
            raise AeonSchemaError(
                "mock must be true without API key (стоп-точка №2): "
                "mock=false без DEEPSEEK_API_KEY запрещён; обход — "
                "force_unsafe=True + force_reason"
            )
        log_event(
            _logger, "aeon_mock_flag_bypassed",
            reason=force_reason,
            operator=os.getenv("AEON_OPERATOR") or _operator(),
            trace_id=trace_id,
        )

    pipeline = pipeline or {"steps_requested": ["extract"],
                            "steps_executed": ["extract"],
                            "steps_halted": [], "steps_failed": []}
    full_traces = {slot: traces.get(slot) for slot in TRACE_SLOTS}

    meta: Dict[str, Any] = {
        "thresholds_snapshot": dict(snapshot),
        "mock": bool(mock),
        "pipeline": pipeline,
    }
    meta.update(metadata or {})

    doc = {
        "aeon_version": "2.0.0",
        "created_at": created_at or datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "generator": GENERATOR,
        "source": dict(source),
        "atom": {
            "content_hash": compute_content_hash(source.get("content", "")),
            "atom_hash": compute_atom_hash(atom),
            "meaning_hash": getattr(atom, "meaning_hash", ""),
            "text": getattr(atom, "source_text", ""),
            "intent": getattr(atom, "intent", ""),
            "domain": getattr(atom, "domain", ""),
            "entities": [_entity_to_dict(e) for e in getattr(atom, "entities", [])],
            "semantic_roles": dict(getattr(atom, "semantic_roles", {}) or {}),
            "primitive_coordinates": list(getattr(atom, "primitive_coordinates", []) or []),
            "complexity": getattr(atom, "complexity", 0.0),
            "urgency": getattr(atom, "urgency", 0.0),
            "extraction_confidence": getattr(atom, "extraction_confidence", 0.0),
            "explanation_chain": list(getattr(atom, "explanation_chain", []) or []),
            "evidence": list(getattr(atom, "evidence", []) or []),
            "confidence_breakdown": dict(getattr(atom, "confidence_breakdown", {}) or {}),
            "language_origin": getattr(atom, "language_origin", ""),
            "is_fragment": getattr(atom, "is_fragment", False),
            "completeness_score": getattr(atom, "completeness_score", 1.0),
            "needs_attention": getattr(atom, "needs_attention", False),
        },
        "traces": full_traces,
        "metadata": meta,
        "extensions": {},
    }
    validate_v2(doc)
    return doc


def write_v2(path, doc: Dict[str, Any]) -> str:
    """Запись v2-документа в файл (JSON, ensure_ascii=False)."""
    validate_v2(doc)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return str(target)


def _entity_to_dict(entity) -> Dict[str, Any]:
    return {
        "name": getattr(entity, "name", ""),
        "type": getattr(entity, "type", "concept"),
        "role": getattr(entity, "role", ""),
        "span": getattr(entity, "span", ""),
        "confidence": getattr(entity, "confidence", 1.0),
        "external_ids": dict(getattr(entity, "external_ids", {}) or {}),
        "external_labels": dict(getattr(entity, "external_labels", {}) or {}),
        "link_confidence": getattr(entity, "link_confidence", 0.0),
        "source_unavailable": getattr(entity, "source_unavailable", False),
        "is_fragment": getattr(entity, "is_fragment", False),
        "completeness_score": getattr(entity, "completeness_score", 1.0),
    }


def _operator() -> str:
    try:
        return os.getlogin()
    except OSError:
        return "unknown"
