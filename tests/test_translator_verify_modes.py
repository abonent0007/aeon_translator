"""Режимы verify_mode в translator (off/basic/full) — mock, 0 сети."""

import pytest

from aeon.embeddings import EmbeddingEngine
from aeon.extractor import MeaningExtractor
from aeon.generator import ExpressionGenerator
from aeon.translator import AeonTranslator
from aeon.verification import VerificationEngine

TEXT = "Сократ признаёт, что ничего не знает. Афины осудили Сократа."

STRUCTURE = {
    "intent": "statement",
    "domain": "philosophy",
    "entities": [
        {"name": "Сократ", "type": "person", "role": "agent",
         "span": "Сократ", "confidence": 0.9},
        {"name": "Афины", "type": "object", "role": "location",
         "span": "Афины", "confidence": 0.85},
    ],
    "semantic_roles": {"agent": "Сократ", "location": "Афины"},
    "evidence": ["Я знаю, что ничего не знаю."],
    "explanation_chain": [
        "Сократ признаёт собственное незнание",
        "Афины осудили Сократа",
    ],
    "confidence_breakdown": {"intent": 0.9, "domain": 0.8, "entities": 0.9, "roles": 0.7},
    "complexity": 0.4,
    "urgency": 0.1,
    "extraction_confidence": 0.85,
    "semantic_tokens": ["мудрость", "суд"],
}

RESPONSES = {
    "Analyze the following text": STRUCTURE,
    "Detective": {"claims": [
        {"claim": "c1", "quote": "Я знаю, что ничего не знаю.", "contradicts": False,
         "confidence": 0.92, "reasoning": "exact quote"},
        {"claim": "c2", "quote": "Афины осудили Сократа", "contradicts": False,
         "confidence": 0.9, "reasoning": "exact quote"},
    ]},
    "Expert": {"claims": [
        {"claim": "c1", "status": "unknown", "source": "",
         "confidence": 0.4, "reasoning": "no external data"},
    ]},
    "Logician": {"contradictions": [], "coherence": 0.9, "reasoning": "ok"},
}


def offline_embeddings():
    engine = EmbeddingEngine()
    engine.available = False
    return engine


@pytest.fixture
def translator(mock_llm):
    mock_llm.responses = RESPONSES
    instance = AeonTranslator(load_embeddings=False)
    instance.embeddings = offline_embeddings()
    instance.llm = mock_llm
    instance.extractor = MeaningExtractor(
        llm_client=mock_llm, embedding_engine=offline_embeddings()
    )
    instance.generator = ExpressionGenerator(llm_client=mock_llm)
    instance.verification = VerificationEngine(llm_client=mock_llm)
    instance.verification.embeddings = offline_embeddings()
    return instance


def test_translator_verify_off(translator):
    result = translator.translate(TEXT, source_language="russian")

    assert result["metadata"]["verification"] is None  # v3.0-поведение


def test_translator_verify_basic(translator):
    result = translator.translate(TEXT, source_language="russian", verify_mode="basic")

    verification = result["metadata"]["verification"]
    assert verification is not None
    assert set(verification["agents"].keys()) == {"detective", "logician"}
    assert len(verification["reasoning_trace"]) == 2


def test_translator_verify_full(translator):
    result = translator.translate(TEXT, source_language="russian", verify_mode="full")

    verification = result["metadata"]["verification"]
    assert set(verification["agents"].keys()) == {"detective", "expert", "logician"}
    assert len(verification["reasoning_trace"]) == 3
    assert verification["cvi"] > 0


def test_translator_legacy_verify_true_maps_to_full(translator):
    result = translator.translate(TEXT, source_language="russian", verify=True)

    verification = result["metadata"]["verification"]
    assert set(verification["agents"].keys()) == {"detective", "expert", "logician"}


def test_translator_language_pack_normalize_hook(translator):
    """Интеграционная точка 2.0: pack.normalize вызывается; None — no-op."""
    calls = []

    class SpyPack:
        iso_code = "grc"

        def normalize(self, text):
            calls.append(text)
            return text

    translator.translate(TEXT, source_language="russian", language_pack=SpyPack())

    assert calls == [TEXT]
