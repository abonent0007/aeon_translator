"""
AEON testing utilities — тестовые дублёры (без сети).

MockLLM — детерминированная замена DeepSeekClient с роутингом ответов
по подстроке запроса. `latency_ms > 0` имитирует сетевую задержку
(используется для замеров производительности в demo без API-ключа).

Использование:
    from aeon.testing import MockLLM
    llm = MockLLM(responses={"Detective": {...}}, latency_ms=200)
"""

import json
import time

from .llm.json_repair import extract_json


class MockLLM:
    """Детерминированный LLM-дублёр."""

    def __init__(self, responses=None, default: str = "{}",
                 available: bool = True, latency_ms: float = 0.0):
        self.available = available
        self.responses = responses or {}
        self.default = default
        self.latency_ms = latency_ms
        self.calls: list = []

    def _resolve(self, messages: list) -> str:
        text = messages[-1].get("content", "") if messages else ""
        for needle, value in self.responses.items():
            if needle in text:
                if isinstance(value, str):
                    return value
                return json.dumps(value, ensure_ascii=False)
        return self.default

    def _call(self, messages: list, temperature: float = 0.7,
              max_tokens: int = 2000) -> str:
        self.calls.append({
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        })
        if self.latency_ms and self.latency_ms > 0:
            time.sleep(self.latency_ms / 1000.0)
        if not self.available:
            return ""
        return self._resolve(messages)

    def _call_json(self, messages: list, temperature: float = 0.3,
                   max_tokens: int = 2000) -> dict:
        raw = self._call(messages, temperature, max_tokens)
        if not raw:
            return {}
        data, reason = extract_json(raw)
        if reason is None:
            return data
        return {"raw_response": raw, "parse_error": reason}

    # ── высокоуровневые операции (зеркало DeepSeekClient) ──

    def translate_text(self, text: str, source_lang: str = "auto",
                       target_lang: str = "english") -> str:
        return self._call([
            {"role": "system", "content": "You are a professional translator."},
            {"role": "user", "content": f"Translate the following text to {target_lang}:\n{text}"},
        ], temperature=0.3).strip()

    def generate_code(self, description: str, target_lang: str) -> str:
        raw = self._call([
            {"role": "system", "content": f"You are an expert {target_lang} programmer."},
            {"role": "user", "content": f"Generate {target_lang} code.\nDescription: {description}"},
        ], temperature=0.3, max_tokens=3000)
        return raw.strip()

    def describe_for_image(self, text: str, style: str = "realistic") -> str:
        return self._call([
            {"role": "system", "content": "You create image generation prompts."},
            {"role": "user", "content": f"Create an image prompt ({style}): {text}"},
        ], temperature=0.8).strip()
