"""TEI-XML экспорт (шаг 3.7, D): inline где возможно (Q3), conditional-inline
morphology (refinement 1: только уникальные формы), standoff остального
(refinement 2: variant_readings — всегда standoff). Namespace + minidom-валидность.
"""

import json
from typing import Any, Dict, List, Tuple
from xml.sax.saxutils import escape, quoteattr

from .common import label_of, legacy_warning, provenance

TEI_NS = "http://www.tei-c.org/ns/1.0"

_ENTITY_TAGS = {"person": "persName", "deity": "persName", "place": "placeName",
                "group": "orgName"}


def _entity_tag(entity_type: Any) -> str:
    return _ENTITY_TAGS.get(str(entity_type or "").lower(), "name")


def _ref_uri(entity: Dict[str, Any]) -> str:
    external = entity.get("external_ids") or {}
    for key, template in (("wikidata", "https://www.wikidata.org/entity/{}"),
                          ("pleiades", "https://pleiades.stoa.org/places/{}"),
                          ("trismegistos", "https://www.trismegistos.org/text/{}")):
        value = external.get(key)
        if value:
            value = str(value)
            return value if value.startswith("http") else template.format(value)
    return ""


def _name_tag(entity: Dict[str, Any]) -> Tuple[str, str]:
    tag = _entity_tag(entity.get("type"))
    attrs = f' type={quoteattr(str(entity.get("type") or "concept"))}'
    ref = _ref_uri(entity)
    if ref:
        attrs += f' ref={quoteattr(ref)}'
    return f"<{tag}{attrs}>", f"</{tag}>"


def _w_tag(form: Dict[str, Any]) -> Tuple[str, str]:
    attrs = ""
    if form.get("lemma"):
        attrs += f' lemma={quoteattr(str(form["lemma"]))}'
    if form.get("pos"):
        pos_slug = "#pos-" + str(form["pos"])
        attrs += f' ana={quoteattr(pos_slug)}'
    return f"<w{attrs}>", "</w>"


def _inline_marks(doc: Dict[str, Any]) -> Tuple[List[Tuple[int, int, str, str]],
                                                List[Dict], List[Dict]]:
    """→ (marks, standoff_entities, standoff_forms). Greedy non-overlap по offset."""
    content = str((doc.get("source") or {}).get("content") or "")
    atom = doc.get("atom") or {}
    traces = doc.get("traces") or {}
    candidates: List[Tuple[int, int, str, str]] = []
    standoff_entities: List[Dict] = []
    for entity in atom.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        span = str(entity.get("span") or "")
        position = content.find(span) if span else -1
        if position < 0:
            standoff_entities.append(dict(entity, standoff_reason="span_not_in_text"))
            continue
        open_tag, close_tag = _name_tag(entity)
        candidates.append((position, position + len(span), open_tag, close_tag))

    morphology = traces.get("morphology")
    forms = []
    if isinstance(morphology, dict) and isinstance(morphology.get("forms"), list):
        forms = [form for form in morphology["forms"] if isinstance(form, dict)]
    elif isinstance(morphology, list):
        forms = [form for form in morphology if isinstance(form, dict)]
    standoff_forms: List[Dict] = []
    for form in forms:
        word = str(form.get("form") or "")
        if not word:
            continue
        if content.count(word) == 1:
            open_tag, close_tag = _w_tag(form)
            position = content.find(word)
            candidates.append((position, position + len(word), open_tag, close_tag))
        else:
            standoff_forms.append(form)

    candidates.sort(key=lambda item: (item[0], -item[1]))
    marks: List[Tuple[int, int, str, str]] = []
    last_end = 0
    for start, end, open_tag, close_tag in candidates:
        if start < last_end:
            continue
        marks.append((start, end, open_tag, close_tag))
        last_end = end
    return marks, standoff_entities, standoff_forms


def _render_inline(content: str, marks: List[Tuple[int, int, str, str]]) -> str:
    parts: List[str] = []
    cursor = 0
    for start, end, open_tag, close_tag in marks:
        parts.append(escape(content[cursor:start]))
        parts.append(open_tag + escape(content[start:end]) + close_tag)
        cursor = end
    parts.append(escape(content[cursor:]))
    return "".join(parts).replace("\n", "\n<lb/>")


def _header(doc: Dict[str, Any], label: str) -> str:
    atom = doc.get("atom") or {}
    source = doc.get("source") or {}
    metadata = doc.get("metadata") or {}
    pipeline = metadata.get("pipeline") or {}
    prov = provenance(doc)
    warning = legacy_warning(doc)
    lines = ["<teiHeader>", "<fileDesc>", "<titleStmt>",
             f"<title>AEON v2 semantic analysis — {escape(label_of(doc, label))}</title>",
             f"<respStmt><resp>exported by</resp><name>{escape(prov['generator'])}</name></respStmt>",
             "<note>author not recorded in .aeon v2</note>",
             "</titleStmt>",
             "<publicationStmt><p>Generated export (not a critical edition).</p></publicationStmt>",
             "<sourceDesc>",
             f"<p>Digital source (language {escape(str(source.get('language') or 'und'))}); "
             f"created_at {escape(prov['created_at'])}; "
             f"content_hash {escape(prov['content_hash'])}.</p>"]
    if warning:
        lines.append(f"<p>{escape(warning)}</p>")
    lines += ["</sourceDesc>", "</fileDesc>",
              "<encodingDesc>",
              f"<p>Pipeline requested: {escape(', '.join(pipeline.get('steps_requested') or []))}; "
              f"executed: {escape(', '.join(pipeline.get('steps_executed') or []))}.</p>"]
    if pipeline.get("steps_halted") or pipeline.get("steps_failed"):
        lines.append(f"<p>halted: {escape(json.dumps(pipeline.get('steps_halted') or [], ensure_ascii=False))}; "
                     f"failed: {escape(json.dumps(pipeline.get('steps_failed') or [], ensure_ascii=False))}.</p>")
    lines += ["</encodingDesc>",
              f"<profileDesc><langUsage><language ident={quoteattr(str(source.get('language') or 'und'))}/>"
              f"</langUsage></profileDesc>",
              "<revisionDesc>",
              f"<change when={quoteattr(prov['created_at'][:10])}>"
              f"{escape(prov['generator'])}; aeon_version {escape(prov['aeon_version'])}; "
              f"atom_hash {escape(prov['atom_hash'])}; meaning_hash {escape(prov['meaning_hash'] or '-')}; "
              f"extractor_contract {escape(prov['extractor_contract'])}</change>",
              "</revisionDesc>", "</teiHeader>"]
    return "\n".join(lines)


def _standoff(doc: Dict[str, Any], standoff_entities: List[Dict],
              standoff_forms: List[Dict]) -> str:
    traces = doc.get("traces") or {}
    lines = ["<standOff>"]
    entries: List[str] = []
    index = 0
    for entity in standoff_entities:
        index += 1
        ref = _ref_uri(entity)
        ref_attr = f" ref={quoteattr(ref)}" if ref else ""
        entries.append(
            f"<annotation xml:id={quoteattr(f'entity-{index}')} type={quoteattr(str(entity.get('type') or 'concept'))}>"
            f"<name{ref_attr}>{escape(str(entity.get('name') or ''))}</name>"
            f"<note>{escape(str(entity.get('standoff_reason') or ''))}</note></annotation>")
    for form in standoff_forms:
        index += 1
        open_tag, close_tag = _w_tag(form)
        entries.append(
            f"<annotation xml:id={quoteattr(f'morph-{index}')} type=\"ambiguous\">"
            f"{open_tag}{escape(str(form.get('form') or ''))}{close_tag}"
            f"<note>multiple occurrences in source — position ambiguous</note></annotation>")
    if entries:
        lines.append("<listAnnotation>" + "".join(entries) + "</listAnnotation>")

    cross = traces.get("cross_references")
    refs = []
    if isinstance(cross, dict) and isinstance(cross.get("refs"), list):
        refs = [ref for ref in cross["refs"] if isinstance(ref, dict)]
    elif isinstance(cross, list):
        refs = [ref for ref in cross if isinstance(ref, dict)]
    if refs:
        links = []
        for ref in refs:
            src = ref.get("source") or {}
            tgt = ref.get("target") or {}
            target = f"{tgt.get('text_id')}#seg{tgt.get('segment_id')}"
            links.append(
                f"<link target={quoteattr(str(target))} "
                f"ana={quoteattr(str(ref.get('kind') or ''))} "
                f"n={quoteattr(str(ref.get('confidence') or ''))}/>")
        lines.append('<linkGrp type="crossReferences" source="#seg1">'
                     + "".join(links) + "</linkGrp>")

    variant = traces.get("variant_readings")
    if isinstance(variant, dict):
        editions = [entry for entry in (variant.get("editions") or [])
                    if isinstance(entry, dict) and entry.get("edition")]
        if editions:
            witnesses = "".join(
                f"<witness xml:id={quoteattr(str(entry['edition']).replace(' ', '_'))}>"
                f"{escape(str(entry['edition']))} ({escape(str(entry.get('year') or 'n.d.'))})</witness>"
                for entry in editions)
            lines.append(f"<listWit>{witnesses}</listWit>")
        loci = [locus for locus in (variant.get("loci") or [])
                if isinstance(locus, dict)]
        if loci:
            items = []
            for position, locus in enumerate(loci, 1):
                readings = " | ".join(
                    f"{reading.get('text', '')} [{', '.join(reading.get('editions') or [])}]"
                    for reading in (locus.get("readings") or [])
                    if isinstance(reading, dict))
                items.append(
                    f"<annotation xml:id={quoteattr(f'app-{position}')} type=\"apparatus\">"
                    f"<note>line {escape(str(locus.get('line') or ''))}: {escape(readings)}</note></annotation>")
            lines.append("<listAnnotation>" + "".join(items) + "</listAnnotation>")
        selected = variant.get("selected") or variant.get("chosen")
        if selected:
            lines.append(
                f"<note type=\"selection\">selected: "
                f"{escape(json.dumps(selected, ensure_ascii=False))}</note>")

    reconstruction = traces.get("reconstruction")
    if reconstruction is not None:
        lines.append("<note type=\"reconstruction\">"
                     + escape(json.dumps(reconstruction, ensure_ascii=False))
                     + "</note>")
    verification = traces.get("verification")
    if verification is not None:
        lines.append("<note type=\"verification\">"
                     + escape(json.dumps(verification, ensure_ascii=False))
                     + "</note>")
    lines.append("</standOff>")
    return "\n".join(lines)


def render_tei(doc: Dict[str, Any], label: str = "") -> str:
    content = str((doc.get("source") or {}).get("content") or "")
    marks, standoff_entities, standoff_forms = _inline_marks(doc)
    inline_text = _render_inline(content, marks)
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<TEI xmlns="{TEI_NS}">',
             _header(doc, label),
             "<text>",
             "<body>",
             f'<p xml:id="seg1">{inline_text}</p>',
             "</body>",
             _standoff(doc, standoff_entities, standoff_forms),
             "</text>",
             "</TEI>",
             ""]
    return "\n".join(parts)
