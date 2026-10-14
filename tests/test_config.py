"""Тесты конфигурации (aeon/config.py): дефолты v3.0, env-override, ошибки."""

import os

import pytest

from aeon.config import ConfigError, load_config


@pytest.fixture
def clean_env(monkeypatch):
    """Убирает AEON_*/DEEPSEEK_* переменные — дефолты становятся детерминированными."""
    for key in list(os.environ):
        if key.startswith("AEON_") or key in ("DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL"):
            monkeypatch.delenv(key, raising=False)
    return monkeypatch


def test_config_defaults_unchanged(clean_env):
    """Без env — значения идентичны текущему поведению v3.0."""
    cfg = load_config()

    # Verification 2.0 — пороги по агентам (утверждены куратором)
    assert cfg.detective.min_confidence == 0.85
    assert cfg.detective.require_quote is True
    assert cfg.expert.min_confidence == 0.75
    assert cfg.expert.min_sources == 2
    assert cfg.logician.min_coherence == 0.60
    assert cfg.logician.max_contradictions == 0
    assert cfg.abstention_threshold == 0.50

    # Legacy-пороги v3.0 (literal-паритет с verification.py)
    assert cfg.legacy_verification.cross_lingual_threshold == 0.65
    assert cfg.legacy_verification.risk_verified_max == 0.15
    assert cfg.legacy_verification.risk_minor_max == 0.35
    assert cfg.legacy_verification.risk_suspect_max == 0.60
    assert cfg.legacy_verification.consistency_weight == 0.5
    assert cfg.legacy_verification.grounding_weight == 0.5

    # Similarity-уровни v3.0 (bridge_minds / align_score)
    assert cfg.similarity.deep == 0.85
    assert cfg.similarity.good == 0.65
    assert cfg.similarity.partial == 0.45

    # LLM / embeddings — дефолты v3.0
    assert cfg.llm.model == "deepseek-chat"
    assert cfg.llm.base_url == "https://api.deepseek.com"
    assert cfg.llm.max_attempts == 3
    assert cfg.llm.retry_backoff_base == 0.5
    assert cfg.llm.timeout_sec == 60.0
    assert cfg.embeddings.model == "multilingual_mini"

    # Entity Linking по умолчанию выключен (v3.0 не имел linking)
    assert cfg.entity_linking.enabled is False
    assert cfg.entity_linking.rate_limit_sec == 1.0
    assert cfg.entity_linking.cache_ttl_days == 7
    assert cfg.entity_linking.max_links_per_atom == 5


def test_config_env_override(clean_env):
    clean_env.setenv("AEON_DETECTIVE_MIN_CONFIDENCE", "0.9")
    clean_env.setenv("AEON_EXPERT_MIN_SOURCES", "3")
    clean_env.setenv("AEON_ABSTENTION_THRESHOLD", "0.6")
    clean_env.setenv("AEON_ENTITY_LINKING", "yes")
    clean_env.setenv("AEON_WIKIDATA_RATE_LIMIT_SEC", "0.5")

    cfg = load_config()
    assert cfg.detective.min_confidence == 0.9
    assert cfg.expert.min_sources == 3
    assert cfg.abstention_threshold == 0.6
    assert cfg.entity_linking.enabled is True
    assert cfg.entity_linking.rate_limit_sec == 0.5


def test_config_invalid_value(clean_env):
    clean_env.setenv("AEON_DETECTIVE_MIN_CONFIDENCE", "abc")
    with pytest.raises(ConfigError, match="AEON_DETECTIVE_MIN_CONFIDENCE"):
        load_config()


def test_config_invalid_bool(clean_env):
    clean_env.setenv("AEON_ENTITY_LINKING", "maybe")
    with pytest.raises(ConfigError, match="AEON_ENTITY_LINKING"):
        load_config()


def test_config_invalid_int(clean_env):
    clean_env.setenv("AEON_EXPERT_MIN_SOURCES", "two")
    with pytest.raises(ConfigError, match="AEON_EXPERT_MIN_SOURCES"):
        load_config()


def test_config_bool_parsing_variants(clean_env):
    for raw, expected in (
        ("1", True), ("TRUE", True), ("on", True), ("Yes", True),
        ("0", False), ("false", False), ("No", False), ("off", False),
    ):
        clean_env.setenv("AEON_ENTITY_LINKING", raw)
        assert load_config().entity_linking.enabled is expected


def test_config_legacy_env_compat(clean_env):
    """DEEPSEEK_* из .env v3.0 подхватываются; AEON_LLM_MODEL имеет приоритет."""
    clean_env.setenv("DEEPSEEK_MODEL", "deepseek-reasoner")
    clean_env.setenv("DEEPSEEK_BASE_URL", "https://proxy.local")
    cfg = load_config()
    assert cfg.llm.model == "deepseek-reasoner"
    assert cfg.llm.base_url == "https://proxy.local"

    clean_env.setenv("AEON_LLM_MODEL", "deepseek-chat")
    assert load_config().llm.model == "deepseek-chat"


def test_module_level_config_exists():
    """CONFIG доступен после импорта пакета (loose-проверка на любой env)."""
    from aeon.config import CONFIG

    assert CONFIG.detective.min_confidence > 0
    assert CONFIG.verification.expert.min_sources >= 1
    assert CONFIG.abstention_threshold > 0
