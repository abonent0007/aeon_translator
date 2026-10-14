"""Тесты contract v1 (2.7.3): detective skip/quote/ratio + build_claims + role-консистентность."""

import unicodedata

import pytest

from aeon.config import DetectiveConfig
from aeon.extractor import role_consistency_violations
from aeon.semantic_atom import SemanticAtom
from aeon.verification import (
    build_claims,
    has_verbatim_anchor,
    is_meta_or_instruction,
)
from aeon.verification.base import VerificationContext
from aeon.verification.detective import DetectiveAgent
from aeon.verification.verdicts import (
    VERDICT_GROUNDED,
    VERDICT_UNVERIFIABLE_MISSING_DATA,
)

SOURCE = "Gallia est omnis dīvīsa in partēs trēs."


def make_detective(mock_llm, ratio=0.7, min_conf=0.85):
    cfg = DetectiveConfig(min_confidence=min_conf, require_quote=True,
                          grounded_ratio_threshold=ratio)
    return DetectiveAgent(mock_llm, cfg)


def ctx(claims, source=SOURCE):
    return VerificationContext(source_text=source, claims=list(claims))


def row(claim, quote, contradicts=False, confidence=0.9):
    return {"claim": claim, "quote": quote, "contradicts": contradicts,
            "confidence": confidence, "reasoning": "r"}


def make_atom(chain, source=SOURCE):
    atom = SemanticAtom(meaning_hash="t", source_text=source)
    atom.explanation_chain = list(chain)
    return atom


# ── defensive-skip ──


def test_defensive_skip_bare_instruction_word():
    assert is_meta_or_instruction("Identify")          # edge: без \s/: — покрыт (\s|:)
    assert is_meta_or_instruction("Note that the verb is finite.")
    assert is_meta_or_instruction("Find X")
    assert is_meta_or_instruction("Step 2: parse the clause")
    assert is_meta_or_instruction("Intent: statement")
    assert is_meta_or_instruction("Domain: philosophy")
    assert not is_meta_or_instruction("Narrator invokes the Muse (ἔννεπε).")


def test_detective_no_semantic_claims_neutral_with_reason(mock_llm):
    detective = make_detective(mock_llm)

    verdict = detective.verify(ctx(["Intent: statement", "Identify the main verb"]))

    assert verdict.verdict == VERDICT_UNVERIFIABLE_MISSING_DATA
    assert "no_semantic_claims" in verdict.reasoning
    assert mock_llm.calls == []  # LLM не вызывался — все claims отсеяны


# ── quote-verify (Q2) ──


def test_detective_hallucinated_quote_rejected(mock_llm):
    mock_llm.responses = {"grounding verifier": {"claims": [
        row("Gallia divided into parts", "nonexistent phrase xyz")]}}
    detective = make_detective(mock_llm)

    verdict = detective.verify(ctx(["claim about Gallia"]))

    assert verdict.verdict == VERDICT_UNVERIFIABLE_MISSING_DATA
    assert verdict.details["hallucinated_quotes"] == 1
    assert verdict.details["claims"][0]["grounded"] is False


def test_detective_quote_nfc_matched(mock_llm):
    source_nfd = unicodedata.normalize("NFD", SOURCE)      # decomposed
    mock_llm.responses = {"grounding verifier": {"claims": [
        row("division claim", "dīvīsa")]}}                 # NFC quote
    detective = make_detective(mock_llm)

    verdict = detective.verify(ctx(["claim (dīvīsa)"], source=source_nfd))

    assert verdict.verdict == VERDICT_GROUNDED
    assert verdict.details["claims"][0]["grounded"] is True


# ── ratio (Q1) ──


def test_detective_grounded_ratio_2_of_3_grounded(mock_llm):
    mock_llm.responses = {"grounding verifier": {"claims": [
        row("c1", "Gallia"), row("c2", "omnis"), row("c3", "")]}}
    detective = make_detective(mock_llm, ratio=0.6)

    verdict = detective.verify(ctx(["a", "b", "c"]))

    assert verdict.verdict == VERDICT_GROUNDED
    assert verdict.confidence == 0.6  # round(2/3 * 0.9)


def test_detective_below_ratio_threshold_abstains(mock_llm):
    mock_llm.responses = {"grounding verifier": {"claims": [
        row("c1", "Gallia"), row("c2", "omnis"), row("c3", "")]}}
    detective = make_detective(mock_llm)  # default 0.7

    verdict = detective.verify(ctx(["a", "b", "c"]))

    assert verdict.verdict == VERDICT_UNVERIFIABLE_MISSING_DATA
    assert verdict.confidence == 0.6667


# ── build_claims ──


def test_build_claims_excludes_meta():
    atom = make_atom(["Intent: statement", "Narrator describes Gallia (Gallia)."])
    assert build_claims(atom) == ["Narrator describes Gallia (Gallia)."]


def test_build_claims_filters_instructions():
    atom = make_atom(["Identify the main verb (est).",
                      "Gallia is divided (dīvīsa)."])
    assert build_claims(atom) == ["Gallia is divided (dīvīsa)."]


def test_claim_without_anchor_skipped():
    atom = make_atom(["Pure english sentence without any anchor.",
                      "Division theme (Gallia)."])
    assert build_claims(atom) == ["Division theme (Gallia)."]
    assert has_verbatim_anchor("Division theme (Gallia).", SOURCE)
    assert not has_verbatim_anchor("Pure english sentence without any anchor.", SOURCE)


# ── role-консистентность (Q3 / Rule 5) ──


def test_semantic_roles_entity_consistency():
    ok = {"entities": [{"name": "Σωκράτης", "role": "agent", "span": "Σωκράτης"}],
          "semantic_roles": {"agent": "Σωκράτης, ἄνδρα"}}  # не-entity разрешён (Q3)
    assert role_consistency_violations(ok) == []

    bad = {"entities": [{"name": "Σωκράτης", "role": "agent", "span": "Σωκράτης"}],
           "semantic_roles": {"agent": "ἄνδρα"}}
    violations = role_consistency_violations(bad)
    assert len(violations) == 1
    assert "Σωκράτης" in violations[0]


def test_strict_role_consistency_env(monkeypatch, mock_llm):
    monkeypatch.setenv("AEON_STRICT_ROLE_CONSISTENCY", "1")
    mock_llm.responses = {"Analyze the following text": {
        "intent": "statement", "domain": "general",
        "entities": [{"name": "X", "type": "person", "role": "agent", "span": "X"}],
        "semantic_roles": {"agent": ""},
        "evidence": ["X est"], "explanation_chain": ["X is asserted (X est)."],
        "confidence_breakdown": {}, "complexity": 0.1, "urgency": 0.1,
        "extraction_confidence": 0.8, "semantic_tokens": [],
    }}
    from aeon.embeddings import EmbeddingEngine
    from aeon.extractor import MeaningExtractor

    engine = EmbeddingEngine()
    engine.available = False
    extractor = MeaningExtractor(llm_client=mock_llm, embedding_engine=engine)

    with pytest.raises(ValueError, match="role consistency"):
        extractor.extract_from_text("X est", "la")
