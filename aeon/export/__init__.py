"""aeon.export — экспорт .aeon v2 в исследовательские форматы (шаг 3.7).

TEI-XML / Markdown / BibTeX (artifact + editions) / JSON-LD.
stdlib-only, offline, детерминизм (docs/phase3_37_scoping.md).
Predictions only: gold-разметка отклоняется (`test_export_rejects_gold_jsonl`).
"""

from .bibtex import render_bibtex_artifact, render_bibtex_editions
from .common import ExportError, label_of, legacy_warning, load_document, provenance
from .jsonld import render_jsonld
from .markdown import render_markdown
from .tei import render_tei

__all__ = [
    "ExportError",
    "load_document",
    "provenance",
    "legacy_warning",
    "label_of",
    "render_markdown",
    "render_tei",
    "render_jsonld",
    "render_bibtex_artifact",
    "render_bibtex_editions",
]
