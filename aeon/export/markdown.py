"""Markdown-экспорт (шаг 3.7): publication-report одного .aeon v2 атома."""

import json
from typing import Any, Dict, List

from .common import label_of, legacy_warning, provenance

_MORPH_COLUMNS = ("form", "lemma", "pos", "tense", "mood", "voice", "person",
                  "case", "number", "gender")


def _cell(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|") \
                                                 .replace("\n", " ")


def _entity_ref(entity: Dict[str, Any]) -> str:
    external = entity.get("external_ids") or {}
    for key in ("wikidata", "pleiades", "trismegistos"):
        value = external.get(key)
        if value:
            return f"{key}:{value}"
    return ""


def _as_forms(morphology: Any) -> List[Dict[str, Any]]:
    if isinstance(morphology, dict):
        forms = morphology.get("forms")
        return forms if isinstance(forms, list) else []
    return morphology if isinstance(morphology, list) else []


def _as_refs(cross: Any) -> List[Dict[str, Any]]:
    if isinstance(cross, dict):
        refs = cross.get("refs")
        return refs if isinstance(refs, list) else []
    return cross if isinstance(cross, list) else []


def _morph_table(forms: List[Dict[str, Any]]) -> List[str]:
    lines = ["| " + " | ".join(_MORPH_COLUMNS) + " |",
             "|" + "---|" * len(_MORPH_COLUMNS)]
    for form in forms:
        lines.append("| " + " | ".join(
            _cell(form.get(column)) for column in _MORPH_COLUMNS) + " |")
    return lines


def render_markdown(doc: Dict[str, Any], label: str = "") -> str:
    atom = doc.get("atom") or {}
    source = doc.get("source") or {}
    traces = doc.get("traces") or {}
    metadata = doc.get("metadata") or {}
    prov = provenance(doc)
    lines: List[str] = [f"# AEON export — {label_of(doc, label)}", ""]

    warning = legacy_warning(doc)
    if warning:
        lines += [f"> **{warning}**", ""]

    lines += ["## Provenance", "", "| field | value |", "|---|---|"]
    for key in ("generator", "aeon_version", "created_at", "content_hash",
                "atom_hash", "meaning_hash", "extractor_contract"):
        if prov[key]:
            lines.append(f"| {key} | {_cell(prov[key])} |")
    lines.append("")

    lines += [f"## Source ({source.get('language') or 'und'})", "",
              "```text", str(source.get("content") or ""), "```", ""]

    lines += ["## Atom", "",
              f"- intent: {atom.get('intent')}",
              f"- domain: {atom.get('domain')}",
              f"- is_fragment: {atom.get('is_fragment')}",
              f"- completeness_score: {atom.get('completeness_score')}",
              f"- extraction_confidence: {atom.get('extraction_confidence')}"]
    explanation = atom.get("explanation_chain") or []
    if explanation:
        lines += ["", "### Explanation chain"] + \
                 [f"- {item}" for item in explanation]
    evidence = atom.get("evidence") or []
    if evidence:
        lines += ["", "### Evidence"] + [f"- {item}" for item in evidence]

    entities = atom.get("entities") or []
    if entities:
        lines += ["", "## Entities", "",
                  "| name | type | role | ref | confidence |",
                  "|---|---|---|---|---|"]
        for entity in entities:
            lines.append(
                f"| {_cell(entity.get('name'))} | {_cell(entity.get('type'))} "
                f"| {_cell(entity.get('role'))} | {_cell(_entity_ref(entity))} "
                f"| {_cell(entity.get('confidence'))} |")

    forms = _as_forms(traces.get("morphology"))
    if forms:
        lines += ["", "## Morphology", ""] + _morph_table(forms)

    reconstruction = traces.get("reconstruction")
    if reconstruction:
        lines += ["", "## Reconstruction", ""]
        if isinstance(reconstruction, dict):
            for key in ("status", "reason", "verdict"):
                if reconstruction.get(key):
                    lines.append(f"- {key}: {reconstruction[key]}")
            hypotheses = reconstruction.get("hypotheses") or []
            for index, hypothesis in enumerate(hypotheses, 1):
                if isinstance(hypothesis, dict):
                    lines.append(
                        f"- hypothesis {index}: "
                        f"{hypothesis.get('text', '')} "
                        f"(confidence {hypothesis.get('confidence')})")
        else:
            lines.append(str(reconstruction))

    variant = traces.get("variant_readings")
    if variant:
        lines += ["", "## Variant readings", ""]
        if isinstance(variant, dict):
            if variant.get("work"):
                lines.append(f"- work: {variant['work']}")
            editions = variant.get("editions") or []
            if editions:
                lines.append("- editions: " + ", ".join(
                    f"{entry.get('edition')} ({entry.get('year')})"
                    for entry in editions if isinstance(entry, dict)))
            selected = variant.get("selected") or variant.get("chosen")
            if selected:
                lines.append(f"- selected: {json.dumps(selected, ensure_ascii=False)}")
        else:
            lines.append(str(variant))

    refs = _as_refs(traces.get("cross_references"))
    if refs:
        lines += ["", "## Cross references", "",
                  "| source | target | kind | confidence | reasoning |",
                  "|---|---|---|---|---|"]
        for ref in refs:
            src = ref.get("source") or {}
            tgt = ref.get("target") or {}
            lines.append(
                f"| {_cell(src.get('text_id'))}/{_cell(src.get('segment_id'))} "
                f"| {_cell(tgt.get('text_id'))}/{_cell(tgt.get('segment_id'))} "
                f"| {_cell(ref.get('kind'))} | {_cell(ref.get('confidence'))} "
                f"| {_cell(ref.get('reasoning'))} |")

    verification = traces.get("verification")
    if verification:
        lines += ["", "## Verification", ""]
        if isinstance(verification, dict):
            combined = verification.get("combined")
            if isinstance(combined, dict):
                lines.append(
                    f"- verdict: {combined.get('verdict')} "
                    f"(cvi {combined.get('cvi')}, reason "
                    f"'{combined.get('reason', '')}')")
            agents = verification.get("agents")
            if isinstance(agents, dict):
                for name, verdict in agents.items():
                    if isinstance(verdict, dict):
                        lines.append(
                            f"- {name}: {verdict.get('verdict')} "
                            f"(confidence {verdict.get('confidence')})")
        else:
            lines.append(str(verification))

    pipeline = metadata.get("pipeline") or {}
    if pipeline:
        lines += ["", "## Pipeline", "",
                  "- requested: " + ", ".join(pipeline.get("steps_requested") or []),
                  "- executed: " + ", ".join(pipeline.get("steps_executed") or [])]
        for key in ("steps_halted", "steps_failed"):
            if pipeline.get(key):
                lines.append(f"- {key}: {json.dumps(pipeline[key], ensure_ascii=False)}")

    lines += ["", "---", f"*Exported from .aeon v2 by {prov['generator']}*", ""]
    return "\n".join(lines)
