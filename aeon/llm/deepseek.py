"""
AEON LLM слой — DeepSeekClient (фасад, обратная совместимость с v3.0).

Публичный интерфейс идентичен v3.0 (`available`, `_call`, `_call_json`,
`extract_meaning`, `translate_text`, `generate_code`, `semantic_compare`,
`describe_for_image`). Внутри: OpenAICompatibleProvider + ретраи + JSON-repair
+ структурное логирование (provider/model/latency_ms/retries/trace_id).
"""

import os
from typing import Optional

from ..config import CONFIG, AeonConfig
from ..logging_config import get_logger, log_event
from .json_repair import extract_json
from .openai_compatible import OpenAICompatibleProvider


class DeepSeekClient:
    """Клиент DeepSeek API (OpenAI-совместимый). Интерфейс — как в v3.0."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        *,
        trace_id: Optional[str] = None,
        config: Optional[AeonConfig] = None,
        client=None,
        sleep=None,
    ):
        cfg = (config or CONFIG).llm
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url or cfg.base_url
        self.model = model or cfg.model
        self.trace_id = trace_id
        self._disable_thinking = bool(getattr(cfg, "disable_thinking", False))

        provider_kwargs = {}
        if sleep is not None:
            provider_kwargs["sleep"] = sleep

        self._provider = OpenAICompatibleProvider(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            name=cfg.provider or "deepseek",
            timeout=cfg.timeout_sec,
            max_attempts=cfg.max_attempts,
            base_delay=cfg.retry_backoff_base,
            trace_id=trace_id,
            client=client,
            **provider_kwargs,
        )
        self._logger = get_logger("aeon.llm")

    # ═══════════════════════════════════════════════════════════
    # Базовые свойства и вызовы (совместимость с v3.0)
    # ═══════════════════════════════════════════════════════════

    @property
    def available(self) -> bool:
        return self._provider.available

    @property
    def client(self):
        return self._provider.client

    @property
    def usage(self) -> dict:
        """Накопительные токены/вызовы (cost-tracking, 2.7.7)."""
        return {
            "calls": self._provider.calls,
            "prompt_tokens": self._provider.prompt_tokens,
            "completion_tokens": self._provider.completion_tokens,
            "cache_hit_tokens": self._provider.cache_hit_tokens,
        }

    def _call(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        trace_id: Optional[str] = None,
    ) -> str:
        """Базовый вызов LLM. "" если клиент недоступен."""
        if not self.available:
            return ""
        extra_body = None
        if self._disable_thinking and str(self.model or "").startswith("deepseek-flash"):
            # 2.7.3-fix: flash — reasoning-модель; без отключения thinking
            # content пуст (finish_reason=length — reasoning съедает max_tokens)
            extra_body = {"thinking": {"type": "disabled"}}
        return self._provider.chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            trace_id=trace_id,
            extra_body=extra_body,
        )

    def _call_json(
        self,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        trace_id: Optional[str] = None,
    ) -> dict:
        """Вызов LLM с ожиданием JSON-ответа (с починкой через json_repair)."""
        raw = self._call(messages, temperature, max_tokens, trace_id=trace_id)
        if not raw:
            return {}

        data, reason = extract_json(raw)
        if reason is None:
            return data

        log_event(
            self._logger,
            "llm_json_parse_failed",
            reason=reason,
            raw_preview=raw[:200],
            trace_id=trace_id or self.trace_id,
        )
        return {"raw_response": raw, "parse_error": reason}

    # ═══════════════════════════════════════════════════════════
    # Высокоуровневые операции (перенесены из v3.0 без изменений)
    # ═══════════════════════════════════════════════════════════

    def extract_meaning(self, text: str, source_lang: str = "auto") -> dict:
        """
        Извлекает семантический смысл из текста с помощью LLM.
        Возвращает структуру: {intent, domain, concepts, complexity, urgency, ...}
        """
        prompt = f"""You are a semantic analysis engine. Analyze the following text and extract its deep meaning.
Respond ONLY with valid JSON, no markdown formatting.

Text: "{text}"
Language: {source_lang}

Return JSON with exactly these fields:
- "intent": one of [question, request, emotion, statement, command, declaration]
- "domain": one of [science, technology, emotion, philosophy, general, art, business]
- "concepts": list of 1-5 key concepts extracted from the text
- "complexity": float 0-1 (how complex/deep the thought is)
- "urgency": float 0-1 (how urgent/important it feels)
- "tone": one of [neutral, positive, negative, urgent, playful, serious]
- "semantic_primitives": list of semantic primitives detected [existence, action, relation, property, quantity, quality, time, space, cause, effect, purpose, means, part, whole, similarity, difference]
- "summary": a concise one-sentence meaning summary in English"""

        return self._call_json([
            {"role": "system", "content": "You are a semantic meaning extractor. Always respond with valid JSON only."},
            {"role": "user", "content": prompt}
        ], temperature=0.3)

    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Переводит текст с сохранением смысла, тона и намерения.
        """
        lang_names = {
            "russian": "Russian", "english": "English", "chinese": "Chinese (Simplified)",
            "auto": "the detected language"
        }
        src = lang_names.get(source_lang, source_lang)
        tgt = lang_names.get(target_lang, target_lang)

        prompt = f"Translate the following text from {src} to {tgt}. Preserve the exact meaning, tone, and intent. Return ONLY the translation, no explanations.\n\nText: {text}"

        return self._call([
            {"role": "system", "content": "You are a professional translator. Translate accurately, preserve meaning and tone. Return only the translation."},
            {"role": "user", "content": prompt}
        ], temperature=0.3).strip()

    def generate_code(self, description: str, target_lang: str) -> str:
        """
        Генерирует код на основе описания намерения.
        """
        prompt = f"""Generate clean, well-structured {target_lang} code based on the following description.
Include helpful docstrings/comments in English.
Return ONLY the code, no markdown formatting, no explanations.

Description: {description}"""

        raw = self._call([
            {"role": "system", "content": f"You are an expert {target_lang} programmer. Generate clean, working code. Return only code, no markdown."},
            {"role": "user", "content": prompt}
        ], temperature=0.3, max_tokens=3000)

        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines)
        return raw

    def semantic_compare(self, text_a: str, text_b: str) -> dict:
        """
        Сравнивает семантическую близость двух текстов.
        """
        prompt = f"""Compare the semantic meaning of these two texts. Return ONLY valid JSON.

Text A: "{text_a}"
Text B: "{text_b}"

Return JSON with:
- "similarity": float 0-1 (semantic similarity score)
- "shared_concepts": list of concepts both texts share
- "understanding": one of ["deep" (similarity > 0.8), "good" (0.5-0.8), "partial" (0.3-0.5), "different" (<0.3)]
- "explanation": brief explanation of the relationship in one sentence"""

        return self._call_json([
            {"role": "system", "content": "You are a semantic comparison engine. Return only valid JSON."},
            {"role": "user", "content": prompt}
        ], temperature=0.2)

    def describe_for_image(self, text: str, style: str = "realistic") -> str:
        """
        Создаёт промпт для генерации изображения на основе текста/эмоции/идеи.
        """
        prompt = f"""Create a detailed image generation prompt in English based on this text/idea/emotion.
Style preference: {style}.
Make it vivid, descriptive, and suitable for high-quality image generation.
Include artistic style, lighting, composition, color palette details.
Maximum 200 words.
Return ONLY the prompt, no explanations.

Text: {text}"""

        return self._call([
            {"role": "system", "content": "You are an expert prompt engineer for image generation. Create detailed, vivid prompts."},
            {"role": "user", "content": prompt}
        ], temperature=0.8).strip()
