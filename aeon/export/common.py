"""Общие утилиты экспорта (шаг 3.7): загрузка, gold-reject, provenance, legacy."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from ..format import AeonSchemaError, load_v2

GOLD_MARKERS = ("expected_atom", "expected_markers", "expected_entities",
                "expected_cross_references")


class ExportError(Exception):
    """Ошибка экспорта: вход не .aeon v2 / gold-разметка / нечитаемый файл."""


def _reject_gold(path: Path, data: Any) -> None:
    if any(marker in data for marker in GOLD_MARKERS):
        raise ExportError(
            f"{path}: gold-разметка не экспортируется "
            f"(predictions only — design G)")


def load_document(path) -> Dict[str, Any]:
    """Загрузка .aeon v2 с reader-валидацией; gold-разметка жёстко отклоняется (G)."""
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError:
        first_line = next((line for line in raw.splitlines() if line.strip()), "")
        try:
            line_doc = json.loads(first_line)
        except json.JSONDecodeError:
            raise ExportError(f"{path}: не .aeon v2 (не JSON)") from None
        _reject_gold(path, line_doc)
        raise ExportError(f"{path}: не .aeon v2 (JSONL-вход)") from None
    _reject_gold(path, doc)
    try:
        return load_v2(path)
    except AeonSchemaError as exc:
        raise ExportError(f"{path}: не .aeon v2 ({exc})") from None


def provenance(doc: Dict[str, Any]) -> Dict[str, str]:
    """Provенанс-выжимка: triple-hash (content/atom/meaning) + контракт (A)."""
    atom = doc.get("atom") or {}
    meta = doc.get("metadata") or {}
    return {
        "aeon_version": str(doc.get("aeon_version") or ""),
        "generator": str(doc.get("generator") or ""),
        "created_at": str(doc.get("created_at") or ""),
        "content_hash": str(atom.get("content_hash") or ""),
        "atom_hash": str(atom.get("atom_hash") or ""),
        "meaning_hash": str(atom.get("meaning_hash") or ""),
        "extractor_contract": str(meta.get("extractor_contract") or ""),
    }


def legacy_warning(doc: Dict[str, Any]) -> Optional[str]:
    """B: legacy-contract warning.

    Триггеры: (1) миграция v1 — `extensions.legacy_v1_original`;
    (2) non-v1 extraction contract — native v2 от 2.7.x
    (`extractor_contract: "v3.0-legacy"`: instructions вместо semantic claims).
    NOTE (эмпирика Plato, стоп №3): `atom.meaning_hash` — штатное v2-поле
    (короткий content-hash, заполняется всегда) — warning НЕ триггерит.
    """
    extensions = doc.get("extensions") or {}
    metadata = doc.get("metadata") or {}
    contract = str(metadata.get("extractor_contract") or "")
    reasons = []
    if extensions.get("legacy_v1_original"):
        reasons.append("migrated from .aeon v1 (extensions.legacy_v1_original)")
    if contract and contract != "v1":
        reasons.append(f"extractor_contract={contract!r} — non-v1 extraction "
                       f"contract (legacy semantic format)")
    if not reasons:
        return None
    return "Legacy contract warning: " + "; ".join(reasons)


def label_of(doc: Dict[str, Any], label: str = "") -> str:
    """Метка документа: CLI --label → язык+короткий atom_hash (text_id в v2 нет)."""
    if label:
        return label
    atom_hash = str((doc.get("atom") or {}).get("atom_hash") or "")
    language = str((doc.get("source") or {}).get("language") or "und")
    return f"{language}:{atom_hash[:12]}" if atom_hash else language
