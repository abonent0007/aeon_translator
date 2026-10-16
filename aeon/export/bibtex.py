"""BibTeX экспорт (шаг 3.7, Q1): artifact-цитата + editions из apparatus.

Split по умолчанию (aeon_artifact.bib + editions.bib); `--bib-split off` —
один файл. Ключи детерминированы (hashlib, без uuid/random — A).
"""

import hashlib
import re
from typing import Any, Dict, List

from .common import label_of, legacy_warning, provenance

EDITION_KEY_PREFIX = "edition"


def _key(prefix: str, seed: str) -> str:
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}:{digest}"


def _escape(value: Any) -> str:
    return str(value if value is not None else "").replace("{", "\\{") \
                                                  .replace("}", "\\}")


def _edition_entries(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    variant = (doc.get("traces") or {}).get("variant_readings")
    if not isinstance(variant, dict):
        return []
    entries = variant.get("editions") or []
    return [entry for entry in entries if isinstance(entry, dict)
            and entry.get("edition")]


def render_bibtex_artifact(doc: Dict[str, Any], label: str = "") -> str:
    prov = provenance(doc)
    year = prov["created_at"][:4] if prov["created_at"] else "n.d."
    lines = ["% AEON export — citable artifact (deterministic; stdlib)",
             f"% source .aeon v2; generator={prov['generator']}; "
             f"aeon_version={prov['aeon_version']}"]
    warning = legacy_warning(doc)
    if warning:
        lines.append(f"% {warning}")
    lines += [
        f"@misc{{{_key('aeon', prov['atom_hash'] or label_of(doc, label))},",
        f"  title = {{AEON v2 semantic analysis: {_escape(label_of(doc, label))}}},",
        "  author = {{AEON v4.0 (automated generator)}},",
        f"  year = {{{_escape(year)}}},",
        "  howpublished = {.aeon v2 document},",
        f"  note = {{content_hash={prov['content_hash']}; "
        f"atom_hash={prov['atom_hash']}; created_at={prov['created_at']}; "
        f"extractor_contract={prov['extractor_contract']}}},",
        "}",
        "",
    ]
    return "\n".join(lines)


def render_bibtex_editions(doc: Dict[str, Any]) -> str:
    entries = _edition_entries(doc)
    if not entries:
        return "% AEON export — editions: none found in this document " \
               "(no variant apparatus)\n"
    lines = ["% AEON export — editions cited in the variant apparatus "
             "(deterministic; stdlib)"]
    for entry in entries:
        edition = str(entry.get("edition") or "")
        year = entry.get("year")
        work = ""
        variant = (doc.get("traces") or {}).get("variant_readings") or {}
        if isinstance(variant, dict):
            work = str(variant.get("work") or "")
        slug = re.sub(r"[^a-z0-9]+", "", edition.lower()) or "edition"
        lines += [
            f"@book{{{EDITION_KEY_PREFIX}:{slug}{f':{year}' if year else ''},",
            f"  editor = {{{_escape(edition)}}},",
            f"  title = {{{_escape(work or 'Source edition')}}},",
            f"  year = {{{_escape(year if year is not None else 'n.d.')}}},",
            "  note = {cited in AEON variant apparatus},",
            "}",
            "",
        ]
    return "\n".join(lines)
