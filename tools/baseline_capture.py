"""Baseline capture (Phase 1.2 master-prompt): deterministic mock scenarios -> baseline.json."""
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from xml.dom import minidom

ROOT = Path('.')
PY = sys.executable


def run(cmd, timeout=600):
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=timeout)
    return result.returncode, result.stdout or ''


def parse_demo(out):
    verdict = re.search(r'CVI: ([\d.]+) \| вердикт: (\w+)', out)
    atom = re.search(r'АТОМ: Atom\(([0-9a-f]+)', out)
    entities = re.search(r'сущностей: (\d+)', out)
    return {
        "verdict": verdict.group(2) if verdict else None,
        "cvi": verdict.group(1) if verdict else None,
        "atom_prefix": atom.group(1)[:8] if atom else None,
        "entities": int(entities.group(1)) if entities else None,
    }


baseline = {"scenarios": {}}

# S1: demo plato mock verify=full
rc, out = run([PY, '-m', 'aeon.demo', '--text',
               'examples/greek/plato_apologia_17a.txt',
               '--verify=full', '--language=grc'])
baseline["scenarios"]["demo_plato_mock"] = {"returncode": rc, **parse_demo(out)}

# S2: demo caesar mock
rc, out = run([PY, '-m', 'aeon.demo', '--text',
               'examples/latin/caesar_bg_1_1.txt', '--language=la'])
baseline["scenarios"]["demo_caesar_mock"] = {"returncode": rc, **parse_demo(out)}

# S3: deterministic v2 fixture -> exports (4 формата)
from aeon.format import build_thresholds_snapshot, dump_v2, load_v2  # noqa: E402
from aeon.export import (render_bibtex_artifact, render_bibtex_editions,  # noqa: E402
                         render_jsonld, render_markdown, render_tei)

content = "μῆνιν ἄειδε θεά"
atom = SimpleNamespace(
    thresholds_snapshot=build_thresholds_snapshot(), source_text=content,
    intent="invocation", domain="literature", entities=[],
    semantic_roles={}, primitive_coordinates=[], complexity=0.1, urgency=0.0,
    extraction_confidence=0.9, explanation_chain=[], evidence=[],
    confidence_breakdown={}, language_origin="grc", is_fragment=False,
    completeness_score=1.0, needs_attention=False, meaning_hash="")
doc = dump_v2(atom,
              source={"content": content, "form": "text", "language": "grc",
                      "normalized": content},
              traces={}, mock=True, created_at="2026-10-16T00:00:00+00:00")
tmp = ROOT / "baseline_fixture.aeon"
tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
loaded = load_v2(tmp)
md = render_markdown(loaded, label="baseline")
tei = render_tei(loaded, label="baseline")
jsonld = render_jsonld(loaded, label="baseline")
bib = render_bibtex_artifact(loaded, label="baseline") + render_bibtex_editions(loaded)
try:
    minidom.parseString(tei)
    tei_ok = True
except Exception:
    tei_ok = False
baseline["scenarios"]["export_fixture"] = {
    "md_section_count": md.count("\n## "),
    "tei_wellformed": tei_ok,
    "tei_length": len(tei),
    "bib_has_misc": "@misc{" in bib,
    "jsonld_context_inline": isinstance(json.loads(jsonld)["@context"], dict),
    "atom_hash_prefix": loaded["atom"]["atom_hash"][:8],
}
tmp.unlink()

# S4: crossrefs mock detect (pair) -> 0 refs
from aeon.crossrefs import CrossReferenceEngine  # noqa: E402
from aeon.testing import MockLLM  # noqa: E402

engine = CrossReferenceEngine(
    llm_client=MockLLM(responses={}, default='{"cross_references": []}'))
refs = engine.detect({"text_id": "a", "segments": ["μῆνιν ἄειδε θεά"]}, "grc",
                     {"text_id": "b", "segments": ["arma virumque cano"]}, "la")
baseline["scenarios"]["crossrefs_mock"] = {"refs": len(refs)}

# S5: gold report mock — ключевые строки summary
rc, out = run([PY, '-m', 'aeon.gold.report', '--dataset',
               'gold/annotations/', '--mode', 'mock'])
keys = [line.strip() for line in out.splitlines()
        if re.search(r'(Markers|Entities|macro F1|is_fragment|Link-level|HEADLINE)',
                     line)]
baseline["scenarios"]["gold_report_mock"] = {"returncode": rc,
                                             "key_lines": keys[:14]}

# S6: v2 roundtrip (dump -> write -> load) — содержание стабильно
baseline["scenarios"]["v2_roundtrip"] = {
    "atom_hash_prefix": doc["atom"]["atom_hash"][:8],
    "content_hash_prefix": doc["atom"]["content_hash"][:8],
    "trace_keys": sorted(doc["traces"].keys()),
}

Path("baseline.json").write_text(
    json.dumps(baseline, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(baseline, ensure_ascii=False, indent=1))
