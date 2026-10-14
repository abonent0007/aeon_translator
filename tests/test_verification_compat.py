"""Обратная совместимость VerificationEngine (v3.0 → 2.0) + trace-связка."""

from aeon.embeddings import EmbeddingEngine
from aeon.verification import VerificationEngine


def offline_embeddings():
    engine = EmbeddingEngine()
    engine.available = False
    return engine


def make_engine(mock_llm):
    engine = VerificationEngine(llm_client=mock_llm)
    engine.embeddings = offline_embeddings()
    return engine


def _grounded_responses():
    return {
        "Detective": {"claims": [
            {"claim": "c1", "quote": "source", "contradicts": False,
             "confidence": 0.95, "reasoning": "ok"},
            {"claim": "c2", "quote": "text", "contradicts": False,
             "confidence": 0.95, "reasoning": "ok"},
        ]},
        "Expert": {"claims": [
            {"claim": "c1", "status": "unknown", "source": "",
             "confidence": 0.4, "reasoning": "no data"},
        ]},
        "Logician": {"contradictions": [], "coherence": 0.9, "reasoning": "ok"},
    }


def test_backward_compat_verify_atom(mock_llm):
    mock_llm.responses = _grounded_responses()
    engine = make_engine(mock_llm)

    result = engine.verify_atom("source text", ["c1", "c2"], ["Name"])

    # legacy-ключи v3.0
    assert "consistency" in result
    assert "score" in result["consistency"]
    assert "flags" in result["consistency"]
    assert isinstance(result["grounding"], dict)
    assert "c1" in result["grounding"]
    assert result["grounding"]["c1"]["grounded"] is True
    assert "hallucination_risk" in result
    assert result["overall_verdict"] in {
        "verified", "minor_issues", "suspect", "likely_hallucination", "unverified",
    }
    # детерминированно: grounded 0.95 + coherent 0.9 → 0.925 → risk 0.075 → verified
    assert result["overall_verdict"] == "verified"
    assert result["hallucination_risk"] == 0.075

    # v4.0-ключи
    assert set(result["agents"].keys()) == {"detective", "expert", "logician"}
    assert result["cvi"] == result["combined"]["overall_confidence"]
    assert result["abstained"] is False
    assert len(result["reasoning_trace"]) == 3


def test_verify_atom_abstained_legacy_verdict(mock_llm):
    mock_llm.responses = {
        "Detective": {"claims": [
            {"claim": "c1", "quote": "", "contradicts": False,
             "confidence": 0.4, "reasoning": "?"},
            {"claim": "c2", "quote": "", "contradicts": False,
             "confidence": 0.4, "reasoning": "?"},
        ]},
        "Expert": {"claims": [
            {"claim": "c1", "status": "unknown", "source": "",
             "confidence": 0.3, "reasoning": "?"},
            {"claim": "c2", "status": "unknown", "source": "",
             "confidence": 0.3, "reasoning": "?"},
        ]},
        "Logician": {"contradictions": [], "coherence": 0.5, "reasoning": "?"},
    }
    engine = make_engine(mock_llm)

    result = engine.verify_atom("src", ["c1", "c2"], [])

    assert result["abstained"] is True
    assert result["overall_verdict"] == "unverified"


def test_trace_id_links_three_verifiers(mock_llm, monkeypatch):
    events = []
    monkeypatch.setattr(
        "aeon.verification.base.log_event",
        lambda logger, msg, **kw: events.append({"msg": msg, **kw}),
    )
    mock_llm.responses = _grounded_responses()
    engine = make_engine(mock_llm)

    engine.verify_atom("source text", ["c1"], ["Name"], trace_id="run-42")

    steps = [event for event in events if event["msg"] == "verification_step"]
    assert len(steps) == 3
    assert all(event["trace_id"] == "run-42" for event in steps)
    assert {event["agent"] for event in steps} == {"detective", "expert", "logician"}


def test_stats_and_verify_cross_lingual_legacy(mock_llm):
    mock_llm.responses = _grounded_responses()
    engine = make_engine(mock_llm)

    engine.verify_atom("source text", ["c1"], [])
    stats = engine.stats()
    assert stats["checks_performed"] == 1
    assert "prevention_rate" in stats

    cross = engine.verify_cross_lingual("текст", "text")
    assert cross["aligned"] is True
    assert cross["pairs"] == {}  # embeddings offline — 0 моделей
