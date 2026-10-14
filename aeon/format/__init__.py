"""
AEON format v2 (шаг 3.1).

Публичный API:
    dump_v2 / write_v2        — writer (snapshot из атома, mock-guard)
    load_v2 / load_v1_and_migrate — reader (+ миграция v1, D2)
    validate_v2 / AeonSchemaError — мини-валидатор (без jsonschema)
    build_thresholds_snapshot — снимок порогов (на момент создания атома, D3)
    compute_content_hash / compute_atom_hash — хэши входа/результата (доп. №2)
    compatibility             — semver-проверка (доп. №4)
"""

from .reader import load_v1_and_migrate, load_v2
from .validator import AeonSchemaError, update_extensions, validate_v2
from .versioning import AeonVersionError, compatibility, parse_version
from .writer import (
    build_thresholds_snapshot,
    compute_atom_hash,
    compute_content_hash,
    dump_v2,
    write_v2,
)

__all__ = [
    "dump_v2",
    "write_v2",
    "load_v2",
    "load_v1_and_migrate",
    "validate_v2",
    "update_extensions",
    "AeonSchemaError",
    "AeonVersionError",
    "compatibility",
    "parse_version",
    "build_thresholds_snapshot",
    "compute_content_hash",
    "compute_atom_hash",
]
