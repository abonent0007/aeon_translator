"""Тесты Latin Pack (шаг 2.2) — 0 сети."""

import unicodedata

import pytest

from aeon.language import registry
from aeon.language.la import LatinPack

PACK = LatinPack()


@pytest.fixture(autouse=True)
def _la_registered():
    registry.register(LatinPack, force=True)
    yield
    registry.clear()


def test_iso_code_and_metadata():
    assert PACK.iso_code == "la"
    assert PACK.display_name == "Latin"
    assert PACK.period == (-200, 1800)
    assert PACK.direction == "ltr"
    PACK.validate()


def test_normalize_nfc_and_jv_policy():
    composed = "āctiō"
    decomposed = unicodedata.normalize("NFD", composed)
    assert PACK.normalize(decomposed) == composed

    # Политика: j/v и i/u НЕ сводятся (сохраняем как в источнике)
    assert PACK.normalize("Iulius") == "Iulius"
    assert PACK.normalize("IVLIVS") == "IVLIVS"
    assert PACK.normalize("vīvō") == "vīvō"


def test_normalize_macrons_preserved():
    text = "Gallia est omnis dīvīsa in partēs trēs"

    assert PACK.normalize(text) == text
    assert "ī" in PACK.normalize(text)


def test_detect_markers_lacuna():
    markers = PACK.detect_markers("text [...] и далее [---]")

    lacunae = [m for m in markers if m.kind == "lacuna"]
    assert len(lacunae) >= 2


def test_detect_markers_editorial():
    markers = PACK.detect_markers("fragmentum <...> et <*>")

    assert [m.kind for m in markers] == ["editorial", "editorial"]


def test_detect_markers_cruces():
    markers = PACK.detect_markers("passage †corruptum† here")

    cruces = [m for m in markers if m.kind == "crux"]
    assert len(cruces) == 1
    assert cruces[0].text == "†corruptum†"


def test_cruces_not_treated_as_lacuna():
    """Стоп-точка 2.2 №2: crux ≠ lacuna (отдельный kind)."""
    markers = PACK.detect_markers("†incertum†")

    kinds = {m.kind for m in markers}
    assert "crux" in kinds
    assert "lacuna" not in kinds


def test_supplement_context():
    markers = PACK.detect_markers("[Caesar] imperator [...]")

    kinds = {m.kind for m in markers}
    assert "supplement" in kinds
    assert "lacuna" in kinds


def test_detect_markers_positions():
    text = "initium [...] finis"

    markers = PACK.detect_markers(text)

    assert text[markers[0].start:markers[0].end] == "[...]"
    assert markers[0].start == len("initium ")


def test_is_fragment_true_on_lacuna():
    assert PACK.is_fragment("dixit [...]") is True


def test_is_fragment_false_on_clean():
    assert PACK.is_fragment("Gallia est omnis divisa") is False


def test_prompts_reference_special_tokens():
    for key in ("extract", "verify", "reconstruct"):
        prompt = PACK.prompts[key]
        assert "[...]" in prompt or "lacuna" in prompt
    assert "†" in PACK.prompts["verify"]
    assert "locus desperatus" in PACK.prompts["verify"]
    assert "no_reconstruction_possible" in PACK.prompts["reconstruct"]


def test_prompts_length_under_30_lines():
    for key, prompt in PACK.prompts.items():
        assert prompt.count("\n") + 1 <= 30, f"промпт {key} длиннее 30 строк"


def test_detect_via_registry():
    pack = registry.detect("Gallia est omnis divisa in partes tres")

    assert pack is not None
    assert pack.iso_code == "la"


def test_detect_ascii_only_returns_none():
    assert registry.detect("hello world") is None


def test_registry_lists_la_after_registration():
    assert "la" in registry.list_available()


def test_end_to_end_translate_with_la_pack(mock_llm, sample_structure):
    from aeon.embeddings import EmbeddingEngine
    from aeon.extractor import MeaningExtractor
    from aeon.generator import ExpressionGenerator
    from aeon.translator import AeonTranslator
    from aeon.verification import VerificationEngine

    def offline_embeddings():
        engine = EmbeddingEngine()
        engine.available = False
        return engine

    mock_llm.responses = {"Analyze the following text": sample_structure}
    translator = AeonTranslator(load_embeddings=False)
    translator.embeddings = offline_embeddings()
    translator.llm = mock_llm
    translator.extractor = MeaningExtractor(
        llm_client=mock_llm, embedding_engine=offline_embeddings()
    )
    translator.generator = ExpressionGenerator(llm_client=mock_llm)
    translator.verification = VerificationEngine(llm_client=mock_llm)
    translator.verification.embeddings = offline_embeddings()

    text = "Gallia est omnis dīvīsa in partēs trēs"
    result = translator.translate(text, source_language="latin",
                                  language_pack=LatinPack())

    assert result["source"]["content"] == text
    assert result["semantic_atom"].source_text == text
