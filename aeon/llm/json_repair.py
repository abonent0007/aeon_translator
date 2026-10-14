"""
AEON LLM слой — извлечение и починка JSON из ответов LLM.

Только stdlib (json + ast + re), без внешних зависимостей.
Чинятся:
  1. markdown fences (```json ... ```, ``` ... ```, незакрытый fence)
  2. текст вокруг JSON ("Вот результат: {...} ...")
  3. trailing commas ({"a": 1,})
  4. Python-литералы: single quotes, True/False/None (через ast)
Неизлечимый ответ → ({}, "unrepairable JSON") — вызывающий сам решает,
что вернуть наружу.
"""

import ast
import json
import re
from typing import Any, Dict, Optional, Tuple

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)\s*```", re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def _strip_fences(raw: str) -> str:
    match = _FENCE_RE.search(raw)
    if match:
        return match.group(1)
    if raw.startswith("```"):
        lines = raw.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines)
    return raw


def _extract_braces(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


def _remove_trailing_commas(text: str) -> str:
    return _TRAILING_COMMA_RE.sub(r"\1", text)


def extract_json(raw: str) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Извлекает JSON-объект из текста ответа LLM.

    Returns:
        (data, None) — при успехе;
        ({}, reason) — если извлечь/починить не удалось.
    """
    if not raw or not raw.strip():
        return {}, "empty response"

    candidate = _extract_braces(_strip_fences(raw.strip()))

    # 1. Чистый JSON
    try:
        data = json.loads(candidate)
        if isinstance(data, dict):
            return data, None
    except json.JSONDecodeError:
        pass

    # 2. Trailing commas
    fixed = _remove_trailing_commas(candidate)
    try:
        data = json.loads(fixed)
        if isinstance(data, dict):
            return data, None
    except json.JSONDecodeError:
        pass

    # 3. Python-литералы (single quotes, True/False/None)
    try:
        data = ast.literal_eval(fixed)
        if isinstance(data, dict):
            return data, None
    except (ValueError, SyntaxError):
        pass

    return {}, "unrepairable JSON"
