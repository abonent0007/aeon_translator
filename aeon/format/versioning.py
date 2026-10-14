"""AEON format — semver-версионирование .aeon (шаг 3.1)."""

import re
from typing import Tuple

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
READER_MAJOR = 2


class AeonVersionError(ValueError):
    """Некорректная semver-строка версии .aeon."""


def parse_version(value: str) -> Tuple[int, int, int]:
    """'X.Y.Z' → (major, minor, patch). Raises AeonVersionError."""
    match = SEMVER_RE.match(str(value or "").strip())
    if not match:
        raise AeonVersionError(f"aeon_version '{value}' не semver (ожидается X.Y.Z)")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def compatibility(version: str) -> str:
    """
    Совместимость reader'а с документом:
      "ok"        — major == 2: читаем как есть (minor игнорируется);
      "migrate"   — major < 2: legacy (v1) — миграционный путь;
      raises AeonVersionError — major > 2 (reader too old).
    """
    major, _minor, _patch = parse_version(version)
    if major > READER_MAJOR:
        raise AeonVersionError(
            f"reader too old: документ v{version}, reader поддерживает "
            f"major {READER_MAJOR} (minor совместим)"
        )
    if major < READER_MAJOR:
        return "migrate"
    return "ok"
