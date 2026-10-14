"""Тесты агентов Verification 2.0 (Детектив/Эксперт/Логик) — mock LLM, 0 сети."""

from aeon.config import CONFIG
from aeon.entity_linking import LinkResult
from aeon.semantic_atom import Entity
from aeon.verification import (
    DetectiveAgent,
    ExpertAgent,
    LogicianAgent,
    VerificationContext,
)
from aeon.verification.verdicts import (
    VERDICT_ABSTAINED,
    VERDICT_COHERENT,
    VERDICT_CONTRADICTED,
    VERDICT_GROUNDED,
    VERDICT_INCOHERENT,
    VERDICT_SUPPORTED,
    VERDICT_UNVERIFIABLE_MISSING_DATA,
    is_negative,
    is_neutral,
)

CFG = CONFIG.verification


def ctx(claims, source="exact source text", **kwargs):
    return VerificationContext(source_text=source, claims=claims, **kwargs)


def make_detective(mock_llm):
    return DetectiveAgent(mock_llm, CFG.detective)


def make_expert(mock_llm, client=None):
    return ExpertAgent(mock_llm, CFG.expert, wikidata_client=client)


def make_logician(mock_llm):
    return LogicianAgent(mock_llm, CFG.logician)


class StubWikidata:
    def __init__(self, link_result=None, source_unavailable=False):
        self._result = link_result
        self._unavailable = source_unavailable

    def link_mention(self, mention, language="en", limit=5):
        if self._unavailable:
            return LinkResult(source_unavailable=True, reason="source_unavailable")
        return self._result or LinkResult(reason="no_candidates")


# ── Детектив ──

def test_detective_grounded(mock_llm):
    mock_llm.responses = {"Detective": {"claims": [
        {"claim": "c1", "quote": "exact source", "contradicts": False,
         "confidence": 0.9, "reasoning": "found"},
    ]}}

    verdict = make_detective(mock_llm).verify(ctx(["c1"]))

    assert verdict.verdict == VERDICT_GROUNDED
    assert verdict.confidence == 0.9
    assert verdict.details["claims"][0]["quote"] == "exact source"


def test_detective_no_quote(mock_llm):
    mock_llm.responses = {"Detective": {"claims": [
        {"claim": "c1", "quote": "", "contradicts": False,
         "confidence": 0.6, "reasoning": "not found"},
    ]}}

    verdict = make_detective(mock_llm).verify(ctx(["c1"]))

    assert verdict.verdict == VERDICT_UNVERIFIABLE_MISSING_DATA
    assert is_neutral(verdict.verdict)
    assert is_negative(verdict.verdict) is False


def test_detective_contradiction(mock_llm):
    mock_llm.responses = {"Detective": {"claims": [
        {"claim": "c1", "quote": "exact", "contradicts": True,
         "confidence": 0.85, "reasoning": "contradicts"},
    ]}}

    verdict = make_detective(mock_llm).verify(ctx(["c1"]))

    assert verdict.verdict == VERDICT_CONTRADICTED
    assert is_negative(verdict.verdict)


def test_detective_low_confidence_abstains(mock_llm):
    mock_llm.responses = {"Detective": {"claims": [
        {"claim": "c1", "quote": "exact", "contradicts": False,
         "confidence": 0.5, "reasoning": "unsure"},
    ]}}

    verdict = make_detective(mock_llm).verify(ctx(["c1"]))

    assert verdict.verdict == VERDICT_ABSTAINED  # 0.5 < min_confidence 0.85


def test_detective_parse_error_abstains(mock_llm):
    mock_llm.default = "I cannot answer."

    verdict = make_detective(mock_llm).verify(ctx(["c1"]))

    assert verdict.verdict == VERDICT_ABSTAINED


# ── Эксперт ──

def test_expert_supported(mock_llm):
    mock_llm.responses = {"Expert": {"claims": [
        {"claim": "c1", "status": "supported", "source": "Q1",
         "confidence": 0.9, "reasoning": "ok"},
        {"claim": "c1", "status": "supported", "source": "Q2",
         "confidence": 0.85, "reasoning": "ok"},
    ]}}
    records = [
        Entity(name="A", external_ids={"wikidata": "Q1"}),
        Entity(name="B", external_ids={"wikidata": "Q2"}),
    ]

    verdict = make_expert(mock_llm).verify(ctx(["c1"], entity_records=records))

    assert verdict.verdict == VERDICT_SUPPORTED
    assert set(verdict.sources) == {"Q1", "Q2"}


def test_expert_contradicted(mock_llm):
    mock_llm.responses = {"Expert": {"claims": [
        {"claim": "c1", "status": "contradicted", "source": "Q1",
         "confidence": 0.8, "reasoning": "refuted"},
    ]}}
    records = [Entity(name="A", external_ids={"wikidata": "Q1"})]

    verdict = make_expert(mock_llm).verify(ctx(["c1"], entity_records=records))

    assert verdict.verdict == VERDICT_CONTRADICTED


def test_expert_source_unavailable_neutral(mock_llm):
    """Стоп-точка 1.3 №2: source_unavailable → нейтрально, НЕ contradicted."""
    stub = StubWikidata(source_unavailable=True)

    verdict = make_expert(mock_llm, client=stub).verify(
        ctx(["c1"], entity_names=["Александр Македонский"])
    )

    assert verdict.verdict == VERDICT_UNVERIFIABLE_MISSING_DATA
    assert is_neutral(verdict.verdict)
    assert is_negative(verdict.verdict) is False


def test_expert_not_enough_sources_neutral(mock_llm):
    mock_llm.responses = {"Expert": {"claims": [
        {"claim": "c1", "status": "supported", "source": "Q1",
         "confidence": 0.9, "reasoning": "ok"},
    ]}}
    records = [Entity(name="A", external_ids={"wikidata": "Q1"})]

    verdict = make_expert(mock_llm).verify(ctx(["c1"], entity_records=records))

    assert verdict.verdict == VERDICT_UNVERIFIABLE_MISSING_DATA
    assert "источник" in verdict.reasoning


def test_expert_unknown_neutral(mock_llm):
    mock_llm.responses = {"Expert": {"claims": [
        {"claim": "c1", "status": "unknown", "source": "",
         "confidence": 0.5, "reasoning": "no data"},
    ]}}

    verdict = make_expert(mock_llm).verify(ctx(["c1"]))

    assert verdict.verdict == VERDICT_UNVERIFIABLE_MISSING_DATA


# ── Логик ──

def test_logician_coherent(mock_llm):
    mock_llm.responses = {"Logician": {"contradictions": [], "coherence": 0.9,
                                       "reasoning": "ok"}}

    verdict = make_logician(mock_llm).verify(ctx(["c1", "c2"]))

    assert verdict.verdict == VERDICT_COHERENT
    assert verdict.confidence == 0.9


def test_logician_contradiction(mock_llm):
    mock_llm.responses = {"Logician": {
        "contradictions": [{"a": "c1", "b": "c2", "explanation": "конфликт"}],
        "coherence": 0.3,
        "reasoning": "conflict",
    }}

    verdict = make_logician(mock_llm).verify(ctx(["c1", "c2"]))

    assert verdict.verdict == VERDICT_INCOHERENT
    assert is_negative(verdict.verdict)


def test_logician_low_coherence_abstains(mock_llm):
    mock_llm.responses = {"Logician": {"contradictions": [], "coherence": 0.5,
                                       "reasoning": "meh"}}

    verdict = make_logician(mock_llm).verify(ctx(["c1", "c2"]))

    assert verdict.verdict == VERDICT_ABSTAINED  # 0.5 < min_coherence 0.6


def test_logician_single_claim_trivially_coherent(mock_llm):
    agent = make_logician(mock_llm)

    verdict = agent.verify(ctx(["only one claim"]))

    assert verdict.verdict == VERDICT_COHERENT
    assert mock_llm.calls == []  # без вызова LLM


def test_agents_abstain_without_llm(mock_llm):
    mock_llm.available = False

    assert make_detective(mock_llm).verify(ctx(["c1"])).verdict == VERDICT_ABSTAINED
    assert make_logician(mock_llm).verify(ctx(["c1", "c2"])).verdict == VERDICT_ABSTAINED
    assert make_expert(mock_llm).verify(ctx(["c1"])).verdict == VERDICT_ABSTAINED
