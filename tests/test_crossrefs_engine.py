"""Тесты crossrefs engine (шаг 3.4.2): промпт, валидация, few-shot инварианты."""

import ast
import json
import unicodedata
from pathlib import Path

import pytest

from aeon.crossrefs import (CONFIDENCE_LEVELS, CROSS_REF_KINDS, FEW_SHOTS,
                            FORMULA_LABELS, PROMPT_VERSION,
                            CrossReferenceEngine, build_prompt)
from aeon.crossrefs.engine import _grounded
from aeon.testing import MockLLM

REPO = Path(__file__).resolve().parent.parent
TEXTS_DIR = REPO / "gold" / "texts"

A = {"text_id": "alpha", "segments": ["μῆνιν ἄειδε θεά"]}
B = {"text_id": "beta", "segments": ["arma virumque cano"]}

PROEM = {"label": "proem_invocation", "description": "sing-verb + addressee"}


def _ref(kind="formulaic_echo", confidence="high", formula=PROEM,
         source=("alpha", 1), target=("beta", 1), pairs=None):
    return {"source": {"text_id": source[0], "segment_id": source[1]},
            "target": {"text_id": target[0], "segment_id": target[1]},
            "kind": kind, "confidence": confidence,
            "matched_lemma_pairs": pairs or [],
            "matched_formula": formula,
            "reasoning": "test"}


def _engine(responses=None, **kwargs):
    return CrossReferenceEngine(
        llm_client=MockLLM(responses=responses or {}, **kwargs))


# ── промпт ──


def test_prompt_contains_inputs_and_closed_set():
    prompt = build_prompt(A, "grc", B, "la")
    assert '"alpha"' in prompt and '"beta"' in prompt
    assert "A1. μῆνιν ἄειδε θεά" in prompt
    assert "B1. arma virumque cano" in prompt
    assert "proem_invocation" in prompt
    assert "specificity beats pair count" in prompt     # v1.1 (D3)
    assert "DIFFERENT authors" in prompt                # v1.1 (D1)
    assert PROMPT_VERSION == "1.2.1"
    assert "TRANSLATION — a version of the source text itself" in prompt  # D7
    assert "do NOT infer clausal correspondence" in prompt                # D7
    assert "OVERRIDE the kind to adaptation" in prompt                    # D7
    assert "SAME author" in prompt                      # v1.2 (D6)
    assert "TEXT_A" in prompt and "TEXT_B" in prompt
    for index in range(1, len(FEW_SHOTS) + 1):
        assert f"--- Example {index} (" in prompt


def test_engine_pair_format_in_prompt():
    llm = MockLLM(responses={}, default='{"cross_references": []}')
    CrossReferenceEngine(llm_client=llm).detect(A, "grc", B, "la")
    sent = llm.calls[0]["messages"][-1]["content"]
    assert "μῆνιν ἄειδε θεά" in sent and '"alpha"' in sent


# ── валидация ──


def test_detect_returns_valid_refs():
    ref = _ref()
    engine = _engine({"μῆνιν": {"cross_references": [ref]}})
    assert engine.detect(A, "grc", B, "la") == [ref]


def test_detect_drops_invalid_entries():
    good = _ref()
    bad_kind = _ref(kind="translation")
    bad_confidence = _ref(confidence="certain")
    echo_no_formula = _ref(formula=None)
    wrong_text_id = _ref(source=("gamma", 1))
    bad_formula_label = _ref(formula={"label": "homeric_invocation",
                                      "description": "x"})
    out_of_range = _ref(target=("beta", 9))

    engine = _engine({"μῆνιν": {"cross_references": [
        good, bad_kind, bad_confidence, echo_no_formula, wrong_text_id,
        bad_formula_label, out_of_range]}})
    assert engine.detect(A, "grc", B, "la") == [good]


def test_detect_rejects_non_list_payload():
    engine = _engine({"μῆνιν": {"cross_references": "not-a-list"}})
    assert engine.detect(A, "grc", B, "la") == []


def test_detect_parse_error_returns_empty():
    engine = _engine({"μῆνιν": "definitely not json"})
    assert engine.detect(A, "grc", B, "la") == []


def test_detect_llm_unavailable_returns_empty():
    engine = _engine({"μῆνιν": {"cross_references": [_ref()]}},
                     available=False)
    assert engine.detect(A, "grc", B, "la") == []


# ── инварианты few-shot / пакета ──


def test_constants_match_gold_loader():
    from aeon.gold.loader import CONFIDENCE_LEVELS as G_CONF
    from aeon.gold.loader import CROSS_REF_KINDS as G_KINDS
    from aeon.gold.loader import FORMULA_LABELS as G_LABELS
    assert G_KINDS == CROSS_REF_KINDS
    assert G_CONF == CONFIDENCE_LEVELS
    assert G_LABELS == FORMULA_LABELS


def _norm(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold().strip()


def _shot_pairs():
    for shot in FEW_SHOTS:
        if shot.get("style") == "contrast":
            for case in shot["cases"]:
                yield case["a"], case["b"]
        else:
            yield shot["a"], shot["b"]


def test_few_shot_not_in_gold_or_scoring():
    corpus_ids = {path.stem for path in TEXTS_DIR.glob("*.txt")}
    gold_blobs = [_norm(path.read_text(encoding="utf-8"))
                  for path in TEXTS_DIR.glob("*.txt")]
    for a, b in _shot_pairs():
        for side in (a, b):
            text_id = side["text_id"]
            assert text_id not in corpus_ids, \
                f"few-shot text_id '{text_id}' в corpus — leak!"
            for segment in side["segments"]:
                normalized = _norm(segment)
                if len(normalized) < 40:
                    continue
                for blob in gold_blobs:
                    assert normalized not in blob, \
                        f"few-shot segment найден в gold-тексте: {text_id}"


def test_crossrefs_package_free_of_gold_imports():
    package = REPO / "aeon" / "crossrefs"
    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("aeon.gold"), \
                        f"{path.name}: import {alias.name}"
                    assert alias.name != "gold"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith("aeon.gold"), \
                    f"{path.name}: from {module}"
                assert ".gold" not in module and module != "gold", \
                    f"{path.name}: from {module}"
                for alias in node.names:
                    assert alias.name != "gold", f"{path.name}: from ... import gold"
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and path.name != "demo.py":
                for needle in ("gold/annotations", "gold/texts", "gold\\texts"):
                    assert needle not in node.value, \
                        f"{path.name}: gold-путь в литерале"


def test_render_examples_roundtrip():
    from aeon.crossrefs import render_examples
    rendered = render_examples()
    for shot in FEW_SHOTS:
        outputs = ([case["output"] for case in shot["cases"]]
                   if shot.get("style") == "contrast" else [shot["output"]])
        for output in outputs:
            assert json.dumps(output, ensure_ascii=False) in rendered


# ── post-filter (countersign refinements 3.4.2) ──


def test_post_filter_len3_uses_needed3():
    """Refinement 1: len>=3 → префикс >= 3 (не 2!); документированная
    коллизия ῥοή/ῥόαι ('ρο'=2) дропается — см. §10 coverage gaps."""
    assert _grounded("θεά", ["θεάων δ' ἔπειτα"])
    assert not _grounded("θεά", ["θέμις ἐστίν"])
    assert not _grounded("ῥοή", ["ῥόαι δ' ὑδάτων"])
    assert not _grounded("in", ["in aqua"])          # len<=2 — не допускается
    assert not _grounded("ἐν", ["ἐν ἄστει"])


def test_post_filter_ungrounded_pair_dropped():
    ref = _ref(kind="adaptation", formula=None, confidence="medium",
               pairs=[{"source_lemma": "cano", "target_lemma": "cano"},
                      {"source_lemma": "vir", "target_lemma": "vir"}])
    engine = _engine({"virum": {"cross_references": [ref]}})
    out = engine.detect({"text_id": "alpha",
                         "segments": ["virum mihi Camena insece versutum"]},
                        "la",
                        {"text_id": "beta",
                         "segments": ["arma virumque cano"]}, "la")
    assert len(out) == 1
    assert out[0]["matched_lemma_pairs"] == [
        {"source_lemma": "vir", "target_lemma": "vir"}]


def test_post_filter_adaptation_without_grounded_pairs_dropped():
    ref = _ref(kind="adaptation", formula=None, confidence="medium",
               pairs=[{"source_lemma": "cano", "target_lemma": "cano"}])
    engine = _engine({"virum": {"cross_references": [ref]}})
    assert engine.detect(
        {"text_id": "alpha", "segments": ["virum mihi Camena insece"]}, "la",
        {"text_id": "beta", "segments": ["arma virumque cano"]}, "la") == []


def test_post_filter_echo_survives_pair_drop():
    ref = _ref(kind="formulaic_echo", pairs=[
        {"source_lemma": "cano", "target_lemma": "cano"}])
    engine = _engine({"virum": {"cross_references": [ref]}})
    out = engine.detect(
        {"text_id": "alpha", "segments": ["virum mihi Camena insece"]}, "la",
        {"text_id": "beta", "segments": ["arma virumque cano"]}, "la")
    assert len(out) == 1
    assert out[0]["matched_lemma_pairs"] == []
    assert out[0]["matched_formula"] == PROEM


def test_demo_refuses_overwrite_without_force(tmp_path):
    """Design principle #18: отказ перезаписи --json-out без --force."""
    from aeon.crossrefs import demo as crossrefs_demo

    src_a = tmp_path / "a.txt"
    src_a.write_text("μῆνιν ἄειδε θεά", encoding="utf-8")
    src_b = tmp_path / "b.txt"
    src_b.write_text("arma virumque cano", encoding="utf-8")
    out = tmp_path / "predictions.json"
    out.write_text("[]", encoding="utf-8")

    with pytest.raises(SystemExit):
        crossrefs_demo.main(["--a", str(src_a), "--b", str(src_b),
                             "--json-out", str(out)])
    assert out.read_text(encoding="utf-8") == "[]"      # не тронут

    crossrefs_demo.main(["--a", str(src_a), "--b", str(src_b),
                         "--json-out", str(out), "--force"])
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["prompt_version"] == PROMPT_VERSION
    assert payload["records"][0]["pair"] == ["a", "b"]


def test_same_author_check_drops():
    """D6 (v1.2): оба author_id заданы и равны → ref дропается."""
    ref = _ref()
    engine = _engine({"μῆνιν": {"cross_references": [ref]}})
    out = engine.detect(
        {"text_id": "alpha", "segments": ["μῆνιν ἄειδε θεά"],
         "author_id": "homer"}, "grc",
        {"text_id": "beta", "segments": ["arma virumque cano"],
         "author_id": "homer"}, "la")
    assert out == []

    different = _engine({"μῆνιν": {"cross_references": [ref]}})
    kept = different.detect(
        {"text_id": "alpha", "segments": ["μῆνιν ἄειδε θεά"],
         "author_id": "homer"}, "grc",
        {"text_id": "beta", "segments": ["arma virumque cano"],
         "author_id": "vergil"}, "la")
    assert kept == [ref]


def test_same_author_check_skips_none():
    """D6: author_id отсутствует у обоих → проверка не применяется."""
    ref = _ref()
    engine = _engine({"μῆνιν": {"cross_references": [ref]}})
    out = engine.detect(
        {"text_id": "alpha", "segments": ["μῆνιν ἄειδε θεά"]}, "grc",
        {"text_id": "beta", "segments": ["arma virumque cano"]}, "la")
    assert out == [ref]
