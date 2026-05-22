"""
DeepSeek LLM клиент — мозг Aeon для извлечения смысла, перевода и генерации кода.
"""

import os
import json
import time
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

try:
    from openai import OpenAI
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False


class DeepSeekClient:
    """
    Клиент DeepSeek API (OpenAI-совместимый).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self._client = None
        self._available = bool(self.api_key and _HAS_OPENAI)

    @property
    def available(self) -> bool:
        return self._available

    @property
    def client(self):
        if self._client is None and self._available:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        return self._client

    def _call(self, messages: list, temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """Базовый вызов LLM."""
        if not self.available:
            return ""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content

    def _call_json(self, messages: list, temperature: float = 0.3, max_tokens: int = 2000) -> dict:
        """Вызов LLM с ожиданием JSON-ответа."""
        raw = self._call(messages, temperature, max_tokens)
        if not raw:
            return {}
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw_response": raw}

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
