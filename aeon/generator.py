"""
Генератор выражений — превращает атом смысла в любую форму.
v2.0: LLM-powered генерация с rule-based fallback.
"""

from typing import Dict, Optional
from .semantic_atom import SemanticAtom
from .extractor import MeaningExtractor
from .llm_client import DeepSeekClient


class ExpressionGenerator:
    """
    Преобразует семантический атом в ЛЮБУЮ форму выражения.
    Использует DeepSeek LLM, с fallback на шаблоны.
    """

    def __init__(self, llm_client: Optional[DeepSeekClient] = None):
        self.llm = llm_client or DeepSeekClient()

    def generate_text(
        self, atom: SemanticAtom, language: str, original_text: str = "", source_lang: str = "auto"
    ) -> str:
        """Генерирует текст на целевом языке."""
        if self.llm.available and original_text:
            return self.llm.translate_text(original_text, source_lang=source_lang, target_lang=language)
        if self.llm.available:
            meaning = self._atom_to_meaning_prompt(atom)
            return self.llm._call([
                {"role": "system", "content": f"Express the following semantic meaning naturally in {language}. Return only the text."},
                {"role": "user", "content": f"Express this meaning naturally: {meaning}"}
            ], temperature=0.7)
        return self._generate_text_template(atom, language)

    def generate_code(
        self, atom: SemanticAtom, language: str, original_text: str = ""
    ) -> str:
        """Генерирует код на целевом языке."""
        if self.llm.available and original_text:
            return self.llm.generate_code(original_text, language)
        if self.llm.available:
            meaning = self._atom_to_meaning_prompt(atom)
            return self.llm.generate_code(meaning, language)
        return self._generate_code_template(atom, language)

    def _atom_to_meaning_prompt(self, atom: SemanticAtom) -> str:
        """Конвертирует атом в осмысленный промпт для LLM."""
        primitives = MeaningExtractor.SEMANTIC_PRIMITIVES
        dominant = [(primitives[i], atom.primitive_coordinates[i])
                    for i in range(len(primitives)) if atom.primitive_coordinates[i] > 0.4]
        concepts = ", ".join(p for p, _ in dominant[:5]) if dominant else "general meaning"
        return (
            f"The core intent is: {atom.intent}. "
            f"The domain is: {atom.domain}. "
            f"Key semantic aspects: {concepts}. "
            f"Emotional tone: {'urgent' if atom.urgency > 0.5 else 'calm'}, "
            f"depth: {'deep' if atom.complexity > 0.6 else 'surface-level'}."
        )

    def generate_visualization(self, atom: SemanticAtom) -> str:
        """Генерирует визуальное представление смысла."""
        primitives = MeaningExtractor.SEMANTIC_PRIMITIVES
        viz = """
┌──────────────────────────────────────────────┐
│         🌌 СЕМАНТИЧЕСКИЙ АТОМ                 │
├──────────────────────────────────────────────┤
"""
        viz += f"│ Хеш: {atom.meaning_hash[:12]}...                  │\n"
        viz += f"│ Намерение: {atom.intent:<15}               │\n"
        viz += f"│ Область:   {atom.domain:<15}               │\n"
        viz += f"│ Сложность: {'█' * int(atom.complexity * 20):20} │\n"
        viz += f"│ Срочность: {'▓' * int(atom.urgency * 20):20} │\n"
        viz += "├──────────────────────────────────────────────┤\n"
        viz += "│ СМЫСЛОВЫЕ КООРДИНАТЫ:                        │\n"

        for i, (primitive, coord) in enumerate(zip(primitives, atom.primitive_coordinates)):
            if abs(coord) > 0.2:
                bar = "█" * int(abs(coord) * 10)
                direction = "+" if coord > 0 else "-"
                viz += f"│ {primitive[:12]:12} {direction}{bar:10} {coord:+.3f} │\n"

        viz += "├──────────────────────────────────────────────┤\n"
        viz += "│ СВЯЗИ С ДРУГИМИ АТОМАМИ:                    │\n"

        if atom.related_atoms:
            for related in atom.related_atoms[:5]:
                viz += f"│ → {related[:20]:20}                    │\n"
        else:
            viz += "│ (изолированный атом)                          │\n"

        viz += "│ Уверенность: {:.0%}                           │\n".format(atom.extraction_confidence)
        viz += "└──────────────────────────────────────────────┘"
        return viz

    def generate_image_prompt(self, atom: SemanticAtom, style: str = "realistic") -> str:
        """Создаёт промпт для генерации изображения."""
        if self.llm.available:
            description = self._atom_to_description(atom)
            return self.llm.describe_for_image(description, style)
        return f"{atom.intent} in {atom.domain} domain, {style} style"

    def _atom_to_description(self, atom: SemanticAtom) -> str:
        """Конвертирует атом в текстовое описание для LLM."""
        parts = [f"Intent: {atom.intent}",
                 f"Domain: {atom.domain}",
                 f"Complexity: {atom.complexity:.2f}",
                 f"Urgency: {atom.urgency:.2f}"]
        primitives = MeaningExtractor.SEMANTIC_PRIMITIVES
        dominant = [(primitives[i], atom.primitive_coordinates[i])
                    for i in range(len(primitives)) if atom.primitive_coordinates[i] > 0.5]
        if dominant:
            parts.append("Key concepts: " + ", ".join(p for p, _ in dominant[:5]))
        return " | ".join(parts)

    def _generate_text_template(self, atom: SemanticAtom, language: str) -> str:
        """Шаблонная генерация текста (fallback)."""
        greetings = {
            "russian": {"question": "Я хочу понять",
                         "statement": "Я думаю, что",
                         "request": "Пожалуйста,",
                         "emotion": "Я чувствую"},
            "english": {"question": "I want to understand",
                         "statement": "I think that",
                         "request": "Please,",
                         "emotion": "I feel"},
            "chinese": {"question": "我想理解",
                         "statement": "我认为",
                         "request": "请",
                         "emotion": "我感觉"}
        }
        lang_greetings = greetings.get(language, greetings["english"])
        greeting = lang_greetings.get(atom.intent, lang_greetings["statement"])
        body = self._generate_body(atom, language)
        expression = f"{greeting} {body}"
        if atom.complexity > 0.7:
            notes = {"russian": "\n\n(Это глубокая мысль, давайте разберём её вместе)",
                     "english": "\n\n(This is a deep thought, let's unpack it together)",
                     "chinese": "\n\n(这是一个深刻的想法，让我们一起探讨)"}
            expression += notes.get(language, "")
        return expression

    def _generate_body(self, atom: SemanticAtom, language: str) -> str:
        primitives = MeaningExtractor.SEMANTIC_PRIMITIVES
        dominant = []
        for i, coord in enumerate(atom.primitive_coordinates):
            if coord > 0.5:
                dominant.append((primitives[i], coord))
        dominant.sort(key=lambda x: x[1], reverse=True)

        phrases = {
            "russian": {"existence": "существует нечто важное",
                         "action": "происходит действие",
                         "relation": "всё связано между собой",
                         "cause": "у этого есть причина",
                         "purpose": "у этого есть цель",
                         "quality": "это имеет особое качество"},
            "english": {"existence": "something important exists",
                         "action": "an action is taking place",
                         "relation": "everything is connected",
                         "cause": "there is a reason for this",
                         "purpose": "this has a purpose",
                         "quality": "this has a special quality"},
            "chinese": {"existence": "重要的事物存在",
                         "action": "行动正在发生",
                         "relation": "万物相连",
                         "cause": "这是有原因的",
                         "purpose": "这是有目的的",
                         "quality": "这有特殊的品质"}
        }
        lang_phrases = phrases.get(language, phrases["english"])

        if dominant:
            top_phrases = [lang_phrases[p] for p, _ in dominant[:3] if p in lang_phrases]
            if top_phrases:
                return ", ".join(top_phrases) + "."
        return "это имеет значение."

    def _generate_code_template(self, atom: SemanticAtom, language: str) -> str:
        """Шаблонная генерация кода (fallback)."""
        if language == "python":
            return f'''"""
AEON Semantic Expression (template fallback)
Intent: {atom.intent}
Domain: {atom.domain}
Complexity: {atom.complexity:.2f}
"""

class Meaning:
    """Выражение семантического атома"""

    def __init__(self):
        self.intent = "{atom.intent}"
        self.domain = "{atom.domain}"
        self.complexity = {atom.complexity:.2f}
        self.confidence = {atom.extraction_confidence:.2f}

    def express(self):
        """Выразить смысл"""
        return {{
            "intent": self.intent,
            "domain": self.domain,
            "understanding": "Смысл выражен в коде"
        }}

meaning = Meaning()
result = meaning.express()
'''
        elif language == "javascript":
            return f'''/**
 * AEON Semantic Expression (template fallback)
 * Intent: {atom.intent}
 * Domain: {atom.domain}
 */

class Meaning {{
    constructor() {{
        this.intent = "{atom.intent}";
        this.domain = "{atom.domain}";
        this.complexity = {atom.complexity:.2f};
    }}

    express() {{
        return {{
            intent: this.intent,
            domain: this.domain,
            understanding: "Смысл выражен в коде"
        }};
    }}
}}

const meaning = new Meaning();
const result = meaning.express();
'''
        else:
            return f'''
◇ АТОМ СМЫСЛА (template fallback)
  Хеш: {atom.meaning_hash}
  Намерение: {atom.intent}
  Область: {atom.domain}
  Сложность: {atom.complexity:.2f}
  Уверенность: {atom.extraction_confidence:.2f}

  Координаты:
    {" ".join(f"{c:+.2f}" for c in atom.primitive_coordinates[:8])}
    {" ".join(f"{c:+.2f}" for c in atom.primitive_coordinates[8:])}
◇
'''
