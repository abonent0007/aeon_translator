"""
AEON format — stdlib мини-валидатор v2 (шаг 3.1, стоп-точка №4).

Scope (намеренно узкий): required-поля / базовые типы / semver /
extensions-overlap. БЕЗ $ref, oneOf, if/then — не реализуем и не будем.
"""

from typing import Any, Dict

from .versioning import AeonVersionError, compatibility

TOP_REQUIRED = (
    "aeon_version", "created_at", "generator", "source", "atom", "traces", "metadata",
)
ATOM_REQUIRED = ("content_hash", "atom_hash", "intent", "domain")
META_REQUIRED = ("thresholds_snapshot", "mock", "pipeline")
PIPELINE_REQUIRED = ("steps_requested", "steps_executed")
CORE_KEYS = frozenset({"aeon_version", "created_at", "generator", "source",
                       "atom", "traces", "metadata", "extensions"})
LEGACY_PREFIX = "legacy_"


class AeonSchemaError(ValueError):
    """Документ нарушает контракт .aeon v2."""


def _require(obj: Dict[str, Any], keys, where: str) -> None:
    missing = [key for key in keys if key not in obj]
    if missing:
        raise AeonSchemaError(f"missing required {where}: {missing}")


def _typecheck(value: Any, expected: type, where: str) -> None:
    if not isinstance(value, expected):
        raise AeonSchemaError(
            f"{where}: ожидался {expected.__name__}, получен {type(value).__name__}"
        )


def validate_extensions(extensions: Dict[str, Any]) -> None:
    """Доп. №3: ключи namespaced (a.b / a_b); core-поля переопределять нельзя."""
    _typecheck(extensions, dict, "extensions")
    for key in extensions:
        if key in CORE_KEYS:
            raise AeonSchemaError(
                f"extensions не может переопределять core-поле '{key}' (доп. №3)"
            )
        if "." not in key and "_" not in key:
            raise AeonSchemaError(
                f"extensions ключ '{key}' должен быть namespaced "
                f"(напр. 'aeon.experiment' или 'acme_metric')"
            )


def validate_v2(doc: Dict[str, Any]) -> None:
    """Проверка v2-документа. Raises AeonSchemaError / AeonVersionError."""
    _typecheck(doc, dict, "document")
    _require(doc, TOP_REQUIRED, "top-level")

    try:
        compatibility(str(doc["aeon_version"]))
    except AeonVersionError as exc:
        raise AeonSchemaError(str(exc)) from exc

    _typecheck(doc["source"], dict, "source")
    _require(doc["source"], ("content", "form", "language"), "source")
    _typecheck(doc["source"]["content"], str, "source.content")

    _typecheck(doc["atom"], dict, "atom")
    _require(doc["atom"], ATOM_REQUIRED, "atom")
    _typecheck(doc["atom"]["content_hash"], str, "atom.content_hash")
    _typecheck(doc["atom"]["atom_hash"], str, "atom.atom_hash")

    _typecheck(doc["traces"], dict, "traces")

    metadata = doc["metadata"]
    _typecheck(metadata, dict, "metadata")
    _require(metadata, META_REQUIRED, "metadata")
    _typecheck(metadata["mock"], bool, "metadata.mock")
    _typecheck(metadata["thresholds_snapshot"], dict, "metadata.thresholds_snapshot")
    if not metadata["thresholds_snapshot"]:
        raise AeonSchemaError("metadata.thresholds_snapshot пуст (доп. №1/стоп №2)")
    _typecheck(metadata["pipeline"], dict, "metadata.pipeline")
    _require(metadata["pipeline"], PIPELINE_REQUIRED, "metadata.pipeline")
    _typecheck(metadata["pipeline"]["steps_requested"], list, "pipeline.steps_requested")
    _typecheck(metadata["pipeline"]["steps_executed"], list, "pipeline.steps_executed")

    # 2b: контрактные метаданные — опциональны (backward compat с 2.7.x),
    # но при наличии проверяются по типу.
    if "chain_language" in metadata and not isinstance(metadata["chain_language"], str):
        raise AeonSchemaError("metadata.chain_language должен быть строкой")
    if ("anchor_language" in metadata
            and metadata["anchor_language"] is not None
            and not isinstance(metadata["anchor_language"], str)):
        raise AeonSchemaError("metadata.anchor_language: строка или null")
    if ("extractor_contract" in metadata
            and not isinstance(metadata["extractor_contract"], str)):
        raise AeonSchemaError("metadata.extractor_contract должен быть строкой")

    validate_extensions(doc.get("extensions") or {})


def update_extensions(doc: Dict[str, Any], updates: Dict[str, Any]) -> None:
    """Доп. D4: legacy_*-ключи immutable — попытка изменения → AeonSchemaError."""
    extensions = doc.setdefault("extensions", {})
    for key, value in updates.items():
        if key.startswith(LEGACY_PREFIX) and key in extensions:
            raise AeonSchemaError(
                f"extensions.{key} immutable (legacy_*): перезапись запрещена"
            )
        extensions[key] = value
    validate_extensions(extensions)
