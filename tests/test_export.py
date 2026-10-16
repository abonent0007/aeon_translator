"""Тесты экспорта .aeon v2 (шаг 3.7): форматы, детерминизм, gold-reject."""

import ast
import json
import unicodedata
from pathlib import Path
from types import SimpleNamespace
from xml.dom import minidom

import pytest

from aeon.export import (ExportError, load_document, render_bibtex_artifact,
                         render_bibtex_editions, render_jsonld,
                         render_markdown, render_tei)
from aeon.format import build_thresholds_snapshot, dump_v2

REPO = Path(__file__).resolve().parent.parent

CONTENT = "μῆνιν ἄειδε θεά\nΠηληϊάδεω Ἀχιλῆος\nθεά"

TRACES = {
    "morphology": {"status": "ok", "forms": [
        {"form": "μῆνιν", "lemma": "μῆνις", "pos": "noun", "tense": None,
         "mood": None, "voice": None, "person": None, "case": "accusative",
         "number": "singular", "gender": "feminine"},
        {"form": "θεά", "lemma": "θεά", "pos": "noun", "tense": None,
         "mood": None, "voice": None, "person": None, "case": "nominative",
         "number": "singular", "gender": "feminine"},
    ]},
    "cross_references": {"prompt_version": "1.2.1", "refs": [
        {"source": {"text_id": "homer_iliad_1", "segment_id": 1},
         "target": {"text_id": "vergil_aen_1", "segment_id": 1},
         "kind": "formulaic_echo", "confidence": "medium",
         "reasoning": "proem formula"},
    ]},
    "variant_readings": {
        "work": "Sappho fr. 31",
        "editions": [{"edition": "Voigt", "year": 1971}],
        "loci": [{"line": 1, "readings": [
            {"text": "φαίνεταί", "editions": ["Voigt"], "note": ""}]}],
        "selected": {"text": "φαίνεταί", "edition": "Voigt",
                     "confidence": 0.71},
    },
    "reconstruction": {"status": "reconstructed",
                       "hypotheses": [{"text": "[ἄειδε]", "confidence": 0.6}]},
    "verification": {"combined": {"verdict": "verified", "cvi": 0.9,
                                  "reason": ""}},
}


def _entity(name, type_, span, qid=None):
    return SimpleNamespace(
        name=name, type=type_, role="agent", span=span, confidence=0.9,
        external_ids=({"wikidata": qid} if qid else {}), external_labels={},
        link_confidence=0.0, source_unavailable=False, is_fragment=False,
        completeness_score=1.0)


def _build_doc(tmp_path, *, content=CONTENT, traces=None, entities=None,
               meaning_hash="", metadata=None, filename="sample.aeon"):
    atom = SimpleNamespace(
        thresholds_snapshot=build_thresholds_snapshot(),
        source_text=content, intent="invocation", domain="literature",
        entities=entities if entities is not None else [
            _entity("Ἀχιλλεύς", "person", "Ἀχιλῆος", qid="Q41746"),
            _entity("Неизвестный", "concept", "нет-в-тексте")],
        semantic_roles={}, primitive_coordinates=[], complexity=0.1,
        urgency=0.0, extraction_confidence=0.9, explanation_chain=["chain"],
        evidence=["ev"], confidence_breakdown={}, language_origin="grc",
        is_fragment=False, completeness_score=1.0, needs_attention=False,
        meaning_hash=meaning_hash)
    doc = dump_v2(atom,
                  source={"content": content, "form": "text",
                          "language": "grc", "normalized": content},
                  traces=dict(TRACES if traces is None else traces),
                  metadata=dict(metadata or {}),
                  mock=True, created_at="2026-10-16T00:00:00+00:00")
    path = tmp_path / filename
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture()
def doc_path(tmp_path):
    return _build_doc(tmp_path)


@pytest.fixture()
def doc(doc_path):
    return load_document(doc_path)


# ── загрузка / gold-reject ──


def test_export_rejects_gold_jsonl(tmp_path):
    gold = tmp_path / "tiny.jsonl"
    record = {"schema_version": "1.2.1", "text_id": "tiny", "language": "grc",
              "segment_id": 1, "segment_text": "x", "expected_atom": {},
              "expected_markers": [], "expected_entities": []}
    gold.write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(ExportError, match="gold"):
        load_document(gold)


def test_load_rejects_non_json(tmp_path):
    path = tmp_path / "bogus.aeon"
    path.write_text("not json at all", encoding="utf-8")
    with pytest.raises(ExportError):
        load_document(path)


# ── markdown ──


def test_markdown_sections(doc):
    text = render_markdown(doc, label="plato")
    assert "# AEON export — plato" in text
    assert "## Source (grc)" in text
    assert "## Entities" in text
    assert "wikidata:Q41746" in text
    assert "## Morphology" in text
    assert "## Cross references" in text
    assert "formulaic_echo" in text
    assert "## Verification" in text
    assert "## Variant readings" in text


# ── tei ──


def test_tei_wellformed_and_inline_entities(doc):
    text = render_tei(doc, label="plato")
    document = minidom.parseString(text)          # well-formedness (D)
    assert 'xmlns="http://www.tei-c.org/ns/1.0"' in text
    assert "<persName" in text                    # inline entity (span найден)
    assert 'ref="https://www.wikidata.org/entity/Q41746"' in text
    assert "teiHeader" in text and "revisionDesc" in text
    assert "Неизвестный" in text                  # standoff fallback
    assert document.documentElement.tagName == "TEI"


def test_morphology_inline_only_when_unique(doc):
    text = render_tei(doc)
    body = text.split("<standOff>")[0]
    # μῆνιν — уникальна → inline <w> в body (ровно один); θεά — 2 вхождения → standoff
    assert body.count("<w ") == 1
    assert 'lemma="μῆνις"' in body
    assert "multiple occurrences in source" in text


def test_variant_readings_standoff_always(doc):
    text = render_tei(doc)
    assert "<listWit>" in text and "Voigt" in text
    assert "<app" not in text                     # refinement 2: без inline <app>
    assert 'type="apparatus"' in text


def test_tei_markers_not_present(doc):
    # H2: v2 не персистит markers → маркерных TEI-элементов нет (не выдумываем)
    text = render_tei(doc)
    for tag in ("<gap", "<supplied", "<unclear", "<sic"):
        assert tag not in text


# ── bibtex ──


def test_bibtex_artifact_and_editions(doc):
    artifact = render_bibtex_artifact(doc, label="plato")
    assert "@misc{" in artifact and "atom_hash=" in artifact
    editions = render_bibtex_editions(doc)
    assert "@book{" in editions and "Voigt" in editions
    assert "1971" in editions


def test_bibtex_editions_none_when_no_apparatus(tmp_path):
    path = _build_doc(tmp_path, traces={"morphology": None}, filename="plain.aeon")
    editions = render_bibtex_editions(load_document(path))
    assert "none found" in editions


# ── jsonld ──


def test_jsonld_inline_context_and_same_as(doc):
    data = json.loads(render_jsonld(doc, label="plato"))
    assert isinstance(data["@context"], dict)      # C: inline @context
    assert data["@id"].startswith("urn:aeon:")
    person = next(node for node in data["aeon:entities"]
                  if node["name"] == "Ἀχιλλεύς")
    assert "wd:Q41746" in person["sameAs"]
    assert person["@type"] == "schema:Person"


# ── legacy-warning (B) ──


def test_legacy_warning_in_outputs(tmp_path):
    """B: warning только для миграционного legacy_v1_original (не meaning_hash)."""
    path = _build_doc(tmp_path, filename="legacy.aeon")
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["extensions"] = {"legacy_v1_original": {"aeon_version": "3.0.0"}}
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    loaded = load_document(path)
    assert "Legacy contract warning" in render_markdown(loaded)
    assert "Legacy contract warning" in render_tei(loaded)
    assert "% Legacy contract warning" in render_bibtex_artifact(loaded)
    # штатный v2 (meaning_hash присутствует) — БЕЗ warning (эмпирика Plato)
    assert "Legacy contract warning" not in render_markdown(
        load_document(_build_doc(tmp_path, filename="fresh.aeon")))


def test_export_warns_on_v30_legacy_contract(tmp_path):
    """Native v2 с extractor_contract='v3.0-legacy' → warning (без миграции)."""
    path = _build_doc(tmp_path, metadata={"extractor_contract": "v3.0-legacy"},
                      filename="v30.aeon")
    loaded = load_document(path)
    assert "Legacy contract warning" in render_markdown(loaded)
    assert "v3.0-legacy" in render_tei(loaded)
    assert "% Legacy contract warning" in render_bibtex_artifact(loaded)


def test_export_no_warning_on_v1_contract(tmp_path):
    """Native v2 с extractor_contract='v1' → БЕЗ warning."""
    loaded = load_document(_build_doc(tmp_path, filename="v1.aeon"))
    assert "Legacy contract warning" not in render_markdown(loaded)
    assert "Legacy contract warning" not in render_tei(loaded)
    assert "% Legacy contract warning" not in render_bibtex_artifact(loaded)


# ── детерминизм (A) ──


def test_export_env_independent(doc, monkeypatch):
    first_md = render_markdown(doc, label="x")
    first_tei = render_tei(doc, label="x")
    monkeypatch.setenv("TZ", "Pacific/Kiritimati")
    monkeypatch.setenv("LANG", "tr_TR.UTF-8")
    monkeypatch.setenv("LC_ALL", "tr_TR.UTF-8")
    assert render_markdown(doc, label="x") == first_md
    assert render_tei(doc, label="x") == first_tei


def test_export_no_impure_calls():
    """A: запрет now/random/uuid в aeon/export (AST-скан)."""
    banned_modules = {"random", "uuid"}
    banned_attrs = {"now", "today", "utcnow"}
    for path in sorted((REPO / "aeon" / "export").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in banned_modules, \
                        f"{path.name}: import {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in banned_modules, \
                    f"{path.name}: from {node.module}"
            elif isinstance(node, ast.Attribute):
                assert node.attr not in banned_attrs, \
                    f"{path.name}: .{node.attr}"


# ── CLI ──


def test_cli_md_collection_and_index(tmp_path):
    from aeon.export import demo as export_demo

    first = _build_doc(tmp_path, filename="one.aeon")
    second = _build_doc(tmp_path, filename="two.aeon")
    out = tmp_path / "out"
    export_demo.main(["--aeon", str(first), str(second),
                      "--format", "md", "--out", str(out)])
    assert (out / "one.md").exists() and (out / "two.md").exists()
    assert (out / "index.md").exists()


def test_cli_bib_split_on_and_off(tmp_path):
    from aeon.export import demo as export_demo

    path = _build_doc(tmp_path, filename="solo.aeon")
    out_on = tmp_path / "on"
    export_demo.main(["--aeon", str(path), "--format", "bib",
                      "--out", str(out_on)])
    assert (out_on / "solo.aeon_artifact.bib").exists()
    assert (out_on / "solo.editions.bib").exists()
    out_off = tmp_path / "off"
    export_demo.main(["--aeon", str(path), "--format", "bib",
                      "--out", str(out_off), "--bib-split", "off"])
    assert (out_off / "solo.bib").exists()
    assert not (out_off / "solo.editions.bib").exists()
