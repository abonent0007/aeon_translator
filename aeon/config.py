"""
AEON v4.0 Configuration — центральная конфигурация.

Принципы:
  1. Дефолты ИДЕНТИЧНЫ поведению v3.0 (обратная совместимость).
  2. Любой параметр переопределяется env-переменной с префиксом AEON_
     (легаси-переменные DEEPSEEK_MODEL / DEEPSEEK_BASE_URL тоже читаются).
  3. Некорректное значение env → ConfigError с понятным сообщением
     (никаких тихих фолбэков).

Использование:
    from aeon.config import CONFIG
    CONFIG.detective.min_confidence          # 0.85
    CONFIG.verification.expert.min_sources   # 2
    CONFIG.abstention_threshold              # 0.50
"""

import os
from dataclasses import dataclass, field
from typing import Optional


class ConfigError(ValueError):
    """Некорректное значение env-переменной AEON_*."""


# ── helpers ──────────────────────────────────────────────────

def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    return raw if raw not in (None, "") else default


def _env_optional_str(name: str, default: Optional[str] = None) -> Optional[str]:
    raw = os.getenv(name)
    return raw if raw not in (None, "") else default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(
            f"Переменная {name}={raw!r}: ожидалось число (float), например 0.85."
        ) from exc


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(
            f"Переменная {name}={raw!r}: ожидалось целое число (int), например 2."
        ) from exc


_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    low = raw.strip().lower()
    if low in _TRUE:
        return True
    if low in _FALSE:
        return False
    raise ConfigError(
        f"Переменная {name}={raw!r}: ожидалось булево значение "
        f"(1/0, true/false, yes/no, on/off)."
    )


# ── секции конфигурации ──────────────────────────────────────

@dataclass(frozen=True)
class DetectiveConfig:
    """Агент «Детектив» (source grounding — точные цитаты из источника)."""

    min_confidence: float = 0.85
    require_quote: bool = True


@dataclass(frozen=True)
class ExpertConfig:
    """Агент «Эксперт» (факт-чек: Wikidata + внешние знания LLM)."""

    min_confidence: float = 0.75
    min_sources: int = 2


@dataclass(frozen=True)
class LogicianConfig:
    """Агент «Логик» (внутренняя связность и непротиворечивость)."""

    min_coherence: float = 0.60
    max_contradictions: int = 0


@dataclass(frozen=True)
class VerificationConfig:
    """Verification 2.0: три независимых агента + калиброванное воздержание."""

    detective: DetectiveConfig = field(default_factory=DetectiveConfig)
    expert: ExpertConfig = field(default_factory=ExpertConfig)
    logician: LogicianConfig = field(default_factory=LogicianConfig)
    abstention_threshold: float = 0.50


@dataclass(frozen=True)
class LegacyVerificationConfig:
    """Пороги v3.0 (сохранены 1:1 для обратной совместимости)."""

    cross_lingual_threshold: float = 0.65   # verify_cross_lingual: >= aligned
    risk_verified_max: float = 0.15         # hallucination_risk < 0.15 → verified
    risk_minor_max: float = 0.35            # < 0.35 → minor_issues
    risk_suspect_max: float = 0.60          # < 0.60 → suspect, иначе likely_hallucination
    consistency_weight: float = 0.5         # risk = 1 - (cons*w + grounding*w)
    grounding_weight: float = 0.5


@dataclass(frozen=True)
class SimilarityConfig:
    """Уровни семантической близости v3.0 (bridge_minds / align_score)."""

    deep: float = 0.85
    good: float = 0.65
    partial: float = 0.45


@dataclass(frozen=True)
class LLMConfig:
    """LLM-провайдер (дефолты v3.0: DeepSeek, OpenAI-совместимый endpoint)."""

    provider: str = "deepseek"
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    temperature_default: float = 0.7
    temperature_json: float = 0.3
    temperature_verification: float = 0.1
    max_attempts: int = 3
    retry_backoff_base: float = 0.5
    timeout_sec: float = 60.0


@dataclass(frozen=True)
class EmbeddingsConfig:
    """Эмбеддинги (дефолт v3.0: paraphrase-multilingual-MiniLM-L12-v2, 384D)."""

    model: str = "multilingual_mini"
    cache_enabled: bool = True


@dataclass(frozen=True)
class EntityLinkingConfig:
    """Entity Linking к Wikidata (новое в v4.0; по умолчанию выключено)."""

    enabled: bool = False
    offline: bool = False                   # True: только кэш, 0 сетевых вызовов
    contact_email: Optional[str] = None     # обязателен в User-Agent Wikidata
    rate_limit_sec: float = 1.0             # ≤1 запрос/сек (лимит куратора)
    cache_ttl_days: int = 7
    cache_path: str = "cache/wikidata.db"
    timeout_sec: float = 10.0
    max_links_per_atom: int = 5
    max_attempts: int = 3                   # ретраи на timeout/5xx
    score_weight_type: float = 0.40         # веса скоринга кандидатов
    score_weight_exactness: float = 0.35
    score_weight_language: float = 0.15
    score_weight_description: float = 0.10

    def __post_init__(self):
        if self.enabled and not self.contact_email:
            raise ConfigError(
                "Entity Linking включён (AEON_ENTITY_LINKING=1), но AEON_CONTACT_EMAIL "
                "не задан. Wikidata требует контакт в User-Agent — укажите email."
            )


@dataclass(frozen=True)
class LoggingConfig:
    """Структурное JSON-lines логирование (см. aeon/logging_config.py)."""

    log_file: str = "logs/aeon.jsonl"
    level: str = "INFO"


@dataclass(frozen=True)
class FragmentsConfig:
    """Fragment Hypothesis Engine (шаг 2.3)."""

    max_hypotheses: int = 4            # 2–4 в промпте; серверный cap
    min_confidence: float = 0.5        # max(conf) ниже → no_reconstruction
    density_threshold: float = 0.005   # markers_count / len(text): ниже — «разреженный»
    verify_hypotheses: bool = True     # каждая гипотеза → Detective


@dataclass(frozen=True)
class AeonConfig:
    """Полная конфигурация AEON v4.0."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    embeddings: EmbeddingsConfig = field(default_factory=EmbeddingsConfig)
    verification: VerificationConfig = field(default_factory=VerificationConfig)
    legacy_verification: LegacyVerificationConfig = field(
        default_factory=LegacyVerificationConfig
    )
    similarity: SimilarityConfig = field(default_factory=SimilarityConfig)
    entity_linking: EntityLinkingConfig = field(default_factory=EntityLinkingConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    fragments: FragmentsConfig = field(default_factory=FragmentsConfig)

    # ── удобный доступ (CONFIG.detective.min_confidence) ──

    @property
    def detective(self) -> DetectiveConfig:
        return self.verification.detective

    @property
    def expert(self) -> ExpertConfig:
        return self.verification.expert

    @property
    def logician(self) -> LogicianConfig:
        return self.verification.logician

    @property
    def abstention_threshold(self) -> float:
        return self.verification.abstention_threshold


# ── сборка из окружения ──────────────────────────────────────

def load_config() -> AeonConfig:
    """Собирает конфигурацию из окружения (AEON_* переопределяет дефолты v3.0)."""
    llm = LLMConfig(
        provider=_env_str("AEON_LLM_PROVIDER", "deepseek"),
        model=_env_str(
            "AEON_LLM_MODEL", _env_str("DEEPSEEK_MODEL", "deepseek-chat")
        ),
        base_url=_env_str(
            "AEON_LLM_BASE_URL",
            _env_str("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        ),
        temperature_default=_env_float("AEON_LLM_TEMPERATURE_DEFAULT", 0.7),
        temperature_json=_env_float("AEON_LLM_TEMPERATURE_JSON", 0.3),
        temperature_verification=_env_float("AEON_LLM_TEMPERATURE_VERIFICATION", 0.1),
        max_attempts=_env_int("AEON_LLM_MAX_ATTEMPTS", 3),
        retry_backoff_base=_env_float("AEON_LLM_RETRY_BACKOFF_BASE", 0.5),
        timeout_sec=_env_float("AEON_LLM_TIMEOUT_SEC", 60.0),
    )

    embeddings = EmbeddingsConfig(
        model=_env_str("AEON_EMBEDDING_MODEL", "multilingual_mini"),
        cache_enabled=_env_bool("AEON_EMBEDDING_CACHE", True),
    )

    verification = VerificationConfig(
        detective=DetectiveConfig(
            min_confidence=_env_float("AEON_DETECTIVE_MIN_CONFIDENCE", 0.85),
            require_quote=_env_bool("AEON_DETECTIVE_REQUIRE_QUOTE", True),
        ),
        expert=ExpertConfig(
            min_confidence=_env_float("AEON_EXPERT_MIN_CONFIDENCE", 0.75),
            min_sources=_env_int("AEON_EXPERT_MIN_SOURCES", 2),
        ),
        logician=LogicianConfig(
            min_coherence=_env_float("AEON_LOGICIAN_MIN_COHERENCE", 0.60),
            max_contradictions=_env_int("AEON_LOGICIAN_MAX_CONTRADICTIONS", 0),
        ),
        abstention_threshold=_env_float("AEON_ABSTENTION_THRESHOLD", 0.50),
    )

    legacy = LegacyVerificationConfig(
        cross_lingual_threshold=_env_float("AEON_LEGACY_CROSS_LINGUAL_THRESHOLD", 0.65),
        risk_verified_max=_env_float("AEON_LEGACY_RISK_VERIFIED_MAX", 0.15),
        risk_minor_max=_env_float("AEON_LEGACY_RISK_MINOR_MAX", 0.35),
        risk_suspect_max=_env_float("AEON_LEGACY_RISK_SUSPECT_MAX", 0.60),
        consistency_weight=_env_float("AEON_LEGACY_CONSISTENCY_WEIGHT", 0.5),
        grounding_weight=_env_float("AEON_LEGACY_GROUNDING_WEIGHT", 0.5),
    )

    similarity = SimilarityConfig(
        deep=_env_float("AEON_SIM_DEEP", 0.85),
        good=_env_float("AEON_SIM_GOOD", 0.65),
        partial=_env_float("AEON_SIM_PARTIAL", 0.45),
    )

    entity_linking = EntityLinkingConfig(
        enabled=_env_bool("AEON_ENTITY_LINKING", False),
        offline=_env_bool("AEON_WIKIDATA_OFFLINE", False),
        contact_email=_env_optional_str("AEON_CONTACT_EMAIL", None),
        rate_limit_sec=_env_float("AEON_WIKIDATA_RATE_LIMIT_SEC", 1.0),
        cache_ttl_days=_env_int("AEON_WIKIDATA_CACHE_TTL_DAYS", 7),
        cache_path=_env_str("AEON_WIKIDATA_CACHE_PATH", "cache/wikidata.db"),
        timeout_sec=_env_float("AEON_WIKIDATA_TIMEOUT_SEC", 10.0),
        max_links_per_atom=_env_int("AEON_MAX_LINKS_PER_ATOM", 5),
        max_attempts=_env_int("AEON_WIKIDATA_MAX_ATTEMPTS", 3),
        score_weight_type=_env_float("AEON_SCORE_WEIGHT_TYPE", 0.40),
        score_weight_exactness=_env_float("AEON_SCORE_WEIGHT_EXACTNESS", 0.35),
        score_weight_language=_env_float("AEON_SCORE_WEIGHT_LANGUAGE", 0.15),
        score_weight_description=_env_float("AEON_SCORE_WEIGHT_DESCRIPTION", 0.10),
    )

    logging_cfg = LoggingConfig(
        log_file=_env_str("AEON_LOG_FILE", "logs/aeon.jsonl"),
        level=_env_str("AEON_LOG_LEVEL", "INFO"),
    )

    fragments_cfg = FragmentsConfig(
        max_hypotheses=_env_int("AEON_FRAGMENT_MAX_HYPOTHESES", 4),
        min_confidence=_env_float("AEON_FRAGMENT_MIN_CONFIDENCE", 0.5),
        density_threshold=_env_float("AEON_FRAGMENT_DENSITY_THRESHOLD", 0.005),
        verify_hypotheses=_env_bool("AEON_FRAGMENT_VERIFY_HYPOTHESES", True),
    )

    return AeonConfig(
        llm=llm,
        embeddings=embeddings,
        verification=verification,
        legacy_verification=legacy,
        similarity=similarity,
        entity_linking=entity_linking,
        logging=logging_cfg,
        fragments=fragments_cfg,
    )


CONFIG = load_config()
