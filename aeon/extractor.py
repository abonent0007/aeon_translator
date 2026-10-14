"""
Извлекатель смысла v3.0 — реальные эмбеддинги + структурированный смысл.
LLM-powered + LaBSE embeddings + entity extraction + роль labelling + explainability.
"""

import hashlib
import re
import json
from typing import List, Dict, Optional
import numpy as np
from .semantic_atom import SemanticAtom, Entity, Relation
from .llm_client import DeepSeekClient
from .embeddings import EmbeddingEngine, get_embedding_engine


class MeaningExtractor:
    """
    Извлекатель смысла v3.0.
    Текст → реальный 768D эмбеддинг + интерпретируемая структура.
    """

    SEMANTIC_PRIMITIVES = [
        "existence", "action", "relation", "property",
        "quantity", "quality", "time", "space",
        "cause", "effect", "purpose", "means",
        "part", "whole", "similarity", "difference"
    ]

    ASSOCIATIONS = {
        "existence": {
            "russian": ["быть", "существовать", "есть", "являться", "жить", "находиться"],
            "english": ["be", "exist", "am", "is", "are", "live"],
            "chinese": ["是", "存在", "在", "有"],
            "code": ["class", "def", "struct", "type", "new", "create"]
        },
        "action": {
            "russian": ["делать", "создавать", "менять", "работать", "запустить", "выполнить"],
            "english": ["do", "make", "create", "run", "execute", "perform"],
            "chinese": ["做", "创造", "运行", "执行"],
            "code": ["run", "execute", "perform", "process", "handle"]
        },
        "relation": {
            "russian": ["связан", "относиться", "принадлежать", "зависеть"],
            "english": ["relate", "connect", "belong", "depend"],
            "chinese": ["关系", "连接", "属于"],
            "code": ["import", "include", "require", "extend", "implement"]
        },
        "property": {
            "russian": ["иметь", "обладать", "свойство", "характеристика"],
            "english": ["have", "property", "attribute", "feature"],
            "chinese": ["有", "属性", "特征"],
            "code": ["self.", "this.", "property", "attr", "field"]
        },
        "quantity": {
            "russian": ["много", "мало", "число", "количество", "все", "несколько"],
            "english": ["many", "few", "number", "count", "all", "some"],
            "chinese": ["多", "少", "数", "几"],
            "code": ["len", "count", "size", "length", "for", "while"]
        },
        "quality": {
            "russian": ["хороший", "плохой", "лучше", "качество", "отличный"],
            "english": ["good", "bad", "better", "quality", "excellent"],
            "chinese": ["好", "坏", "质量", "优秀"],
            "code": ["best", "optimal", "efficient", "quality"]
        },
        "time": {
            "russian": ["сейчас", "потом", "всегда", "время", "когда"],
            "english": ["now", "then", "always", "time", "when"],
            "chinese": ["现在", "然后", "时间", "当"],
            "code": ["time", "sleep", "wait", "async", "delay"]
        },
        "space": {
            "russian": ["здесь", "там", "везде", "место", "где"],
            "english": ["here", "there", "everywhere", "place", "where"],
            "chinese": ["这里", "那里", "地方", "哪里"],
            "code": ["local", "global", "scope", "namespace"]
        },
        "cause": {
            "russian": ["потому", "причина", "из-за", "почему"],
            "english": ["because", "cause", "reason", "why"],
            "chinese": ["因为", "原因", "为什么"],
            "code": ["if", "when", "condition", "trigger"]
        },
        "effect": {
            "russian": ["поэтому", "следовательно", "значит", "результат"],
            "english": ["therefore", "thus", "result", "consequence"],
            "chinese": ["所以", "因此", "结果"],
            "code": ["return", "yield", "result", "output"]
        },
        "purpose": {
            "russian": ["чтобы", "для", "цель", "задача", "миссия"],
            "english": ["goal", "purpose", "mission", "objective", "aim"],
            "chinese": ["目标", "目的", "为了"],
            "code": ["goal", "target", "objective", "purpose"]
        },
        "means": {
            "russian": ["используя", "посредством", "инструмент", "метод"],
            "english": ["using", "tool", "method", "means"],
            "chinese": ["用", "工具", "方法"],
            "code": ["using", "with", "via", "through"]
        },
        "part": {
            "russian": ["часть", "элемент", "компонент", "кусок"],
            "english": ["part", "element", "component", "piece"],
            "chinese": ["部分", "组件", "元素"],
            "code": ["module", "component", "part", "element"]
        },
        "whole": {
            "russian": ["целое", "полный", "весь", "система"],
            "english": ["whole", "entire", "system", "complete"],
            "chinese": ["整体", "全", "系统"],
            "code": ["system", "whole", "complete", "full"]
        },
        "similarity": {
            "russian": ["похожий", "подобный", "как", "аналогичный"],
            "english": ["similar", "like", "same", "analogous"],
            "chinese": ["相似", "像", "同"],
            "code": ["==", "equals", "similar", "match"]
        },
        "difference": {
            "russian": ["разный", "отличаться", "другой", "иначе"],
            "english": ["different", "other", "else", "unlike"],
            "chinese": ["不同", "其他", "别"],
            "code": ["!=", "diff", "else", "other"]
        }
    }

    def __init__(self, llm_client: Optional[DeepSeekClient] = None,
                 embedding_engine: Optional[EmbeddingEngine] = None):
        self.llm = llm_client or DeepSeekClient()
        self.embeddings = embedding_engine or get_embedding_engine()

    # ═══════════════════════════════════════════════════════════
    # Главные методы извлечения
    # ═══════════════════════════════════════════════════════════

    def extract_from_text(self, text: str, language: str = "auto") -> SemanticAtom:
        """Извлекает смысл из текста: реальные эмбеддинги + структура."""
        detected_lang = self._detect_language(text) if language == "auto" else language

        # 1. Реальный эмбеддинг (LaBSE, 768D)
        embedding = self._get_real_embedding(text)

        # 2. Интерпретируемые координаты (16 примитивов)
        prim_coords = self._text_to_coordinates(text, detected_lang)

        # 3. Глубокое структурированное извлечение (LLM)
        structure = self._extract_structure_llm(text, detected_lang)

        # 4. Сущности и роли (из LLM-результата)
        entities = self._parse_entities(structure)
        roles = structure.get("semantic_roles", {})
        evidence = structure.get("evidence", [])
        explanation = structure.get("explanation_chain", [])
        confidence_bd = structure.get("confidence_breakdown", {})

        # 5. Семантические токены
        tokens = structure.get("semantic_tokens", [])

        return SemanticAtom(
            meaning_hash=hashlib.sha256(text.encode()).hexdigest()[:16],
            source_text=text,
            embedding=list(embedding) if embedding is not None else [],
            primitive_coordinates=prim_coords,
            intent=structure.get("intent", "statement"),
            domain=structure.get("domain", "general"),
            entities=entities,
            semantic_roles=roles,
            complexity=structure.get("complexity", self._estimate_complexity(text)),
            urgency=structure.get("urgency", self._estimate_urgency(text)),
            extraction_confidence=structure.get("extraction_confidence", 0.88),
            explanation_chain=explanation,
            evidence=evidence,
            confidence_breakdown=confidence_bd,
            language_origin=detected_lang,
            semantic_tokens=tokens
        )

    def extract_from_code(self, code: str, language: str = "python") -> SemanticAtom:
        """Извлекает смысл из кода."""
        embedding = self._get_real_embedding(code)
        structure = self._analyze_code(code)
        prim_coords = self._code_to_coordinates(structure)

        return SemanticAtom(
            meaning_hash=hashlib.sha256(code.encode()).hexdigest()[:16],
            source_text=code,
            embedding=list(embedding) if embedding is not None else [],
            primitive_coordinates=prim_coords,
            intent=self._extract_code_intent(structure),
            domain="computation",
            complexity=min(1.0, structure.get("complexity", 0.5)),
            urgency=0.5,
            extraction_confidence=0.85,
            language_origin=language
        )

    def extract_from_emotion(self, description: str) -> SemanticAtom:
        """Извлекает смысл из эмоционального описания."""
        embedding = self._get_real_embedding(description)
        detected_lang = self._detect_language(description)
        prim_coords = self._emotion_to_coordinates(description)

        return SemanticAtom(
            meaning_hash=hashlib.sha256(description.encode()).hexdigest()[:16],
            source_text=description,
            embedding=list(embedding) if embedding is not None else [],
            primitive_coordinates=prim_coords,
            intent="express_emotion",
            domain="emotion",
            complexity=0.3,
            urgency=0.7,
            extraction_confidence=0.80,
            language_origin=detected_lang
        )

    # ═══════════════════════════════════════════════════════════
    # Реальные эмбеддинги
    # ═══════════════════════════════════════════════════════════

    def _get_real_embedding(self, text: str) -> Optional[np.ndarray]:
        if self.embeddings.available:
            return self.embeddings.encode(text)
        return None

    # ═══════════════════════════════════════════════════════════
    # Глубокое структурированное извлечение (LLM)
    # ═══════════════════════════════════════════════════════════

    def _extract_structure_llm(self, text: str, language: str) -> dict:
        """LLM извлекает полную семантическую структуру."""
        if not self.llm.available:
            return self._extract_structure_rule(text, language)

        prompt = f"""Analyze the following text deeply. Return ONLY valid JSON (no markdown).

TEXT: "{text}"
LANGUAGE: {language}

Return a JSON object with these fields:
- "intent": one of [question, request, emotion, statement, command, declaration]
- "domain": one of [science, technology, emotion, philosophy, general, art, business, politics]
- "entities": list of objects with {{"name", "type": concept|person|object|action|property|abstract, "role": agent|patient|instrument|location|time|manner|goal, "span": exact text span}}
- "semantic_roles": object with keys [agent, patient, instrument, location, time, goal, manner] and string values
- "semantic_primitives": list of detected primitives [existence, action, relation, property, quantity, quality, time, space, cause, effect, purpose, means, part, whole, similarity, difference]
- "evidence": list of 2-4 exact quotes from the text supporting the analysis
- "explanation_chain": list of 3-5 step-by-step reasoning steps showing HOW you arrived at the analysis
- "confidence_breakdown": object with scores 0-1 for {{"intent", "domain", "entities", "roles"}}
- "complexity": float 0-1
- "urgency": float 0-1
- "extraction_confidence": float 0-1
- "semantic_tokens": list of 3-10 key semantic tokens/concepts"""

        result = self.llm._call_json([
            {"role": "system", "content": "You are a semantic structure analyzer. Return ONLY valid JSON. No markdown, no explanations outside JSON."},
            {"role": "user", "content": prompt}
        ], temperature=0.2, max_tokens=2000)

        return result if result else self._extract_structure_rule(text, language)

    def _extract_structure_rule(self, text: str, language: str) -> dict:
        """Rule-based структура (fallback)."""
        return {
            "intent": self._extract_intent(text),
            "domain": self._extract_domain(text),
            "entities": [],
            "semantic_roles": {},
            "semantic_primitives": [],
            "evidence": [text[:100]],
            "explanation_chain": ["Keyword-based extraction (no LLM)"],
            "confidence_breakdown": {"intent": 0.6, "domain": 0.6, "entities": 0.3, "roles": 0.3},
            "complexity": self._estimate_complexity(text),
            "urgency": self._estimate_urgency(text),
            "extraction_confidence": 0.55,
            "semantic_tokens": []
        }

    def _parse_entities(self, structure: dict) -> List[Entity]:
        entities = []
        for e in structure.get("entities", []):
            entities.append(Entity(
                name=e.get("name", "?"),
                type=e.get("type", "concept"),
                role=e.get("role", ""),
                confidence=e.get("confidence", 0.8),
                span=e.get("span", "")
            ))
        return entities

    # ═══════════════════════════════════════════════════════════
    # Языковая детекция
    # ═══════════════════════════════════════════════════════════

    def _detect_language(self, text: str) -> str:
        text_lower = text.lower()
        if any('\u4e00' <= char <= '\u9fff' for char in text):
            return "chinese"
        if any(char in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя' for char in text_lower):
            return "russian"
        code_indicators = ['def ', 'function', 'class ', 'import ', 'const ', 'let ', 'var ']
        if any(indicator in text for indicator in code_indicators):
            return "code"
        return "english"

    # ═══════════════════════════════════════════════════════════
    # Примитивные координаты (интерпретируемость)
    # ═══════════════════════════════════════════════════════════

    def _text_to_coordinates(self, text: str, language: str) -> List[float]:
        text_lower = text.lower()
        coordinates = []
        for primitive in self.SEMANTIC_PRIMITIVES:
            words = self.ASSOCIATIONS.get(primitive, {})
            all_words = []
            for lang_words in words.values():
                all_words.extend(lang_words)
            score = 0
            for word in all_words:
                if word in text_lower:
                    score += 1
            normalized = min(1.0, score / max(len(all_words) * 0.2, 1))
            coordinates.append(normalized)
        return coordinates

    def _code_to_coordinates(self, structure: Dict) -> List[float]:
        return [
            min(1.0, (structure["classes"] + structure["functions"]) / 10),
            min(1.0, (structure["loops"] + structure["conditionals"]) / 10),
            min(1.0, structure["imports"] / 10),
            min(1.0, structure["functions"] / 10),
            min(1.0, structure["loops"] / 10),
            min(1.0, structure["classes"] / 5),
            0.1, 0.1,
            min(1.0, structure["conditionals"] / 10),
            min(1.0, structure["functions"] / 10),
            0.7, 0.5, 0.3, 0.6, 0.2, 0.4
        ]

    def _emotion_to_coordinates(self, description: str) -> List[float]:
        emotion_vectors = {
            "радость": [0.8, 0.6, 0.3, 0.1, 0.9, 0.7, 0.2, 0.1, 0.4, 0.5, 0.9, 0.3, 0.1, 0.8, 0.2, 0.6],
            "joy": [0.8, 0.6, 0.3, 0.1, 0.9, 0.7, 0.2, 0.1, 0.4, 0.5, 0.9, 0.3, 0.1, 0.8, 0.2, 0.6],
            "грусть": [-0.5, -0.3, -0.7, 0.8, -0.2, -0.6, 0.9, 0.3, -0.4, -0.7, -0.1, 0.2, 0.5, -0.3, 0.7, -0.5],
            "sadness": [-0.5, -0.3, -0.7, 0.8, -0.2, -0.6, 0.9, 0.3, -0.4, -0.7, -0.1, 0.2, 0.5, -0.3, 0.7, -0.5],
            "гнев": [-0.7, 0.8, -0.5, -0.3, 0.9, -0.4, 0.6, 0.2, -0.8, 0.7, -0.3, -0.5, 0.4, -0.6, 0.5, -0.2],
            "anger": [-0.7, 0.8, -0.5, -0.3, 0.9, -0.4, 0.6, 0.2, -0.8, 0.7, -0.3, -0.5, 0.4, -0.6, 0.5, -0.2],
            "любовь": [0.9, 0.5, 0.8, 0.2, 0.7, 0.9, 0.1, 0.3, 0.5, 0.6, 0.9, 0.4, 0.2, 0.9, 0.1, 0.7],
            "love": [0.9, 0.5, 0.8, 0.2, 0.7, 0.9, 0.1, 0.3, 0.5, 0.6, 0.9, 0.4, 0.2, 0.9, 0.1, 0.7],
            "интерес": [0.3, 0.7, 0.5, 0.2, 0.8, 0.6, 0.1, 0.4, 0.3, 0.5, 0.7, 0.4, 0.2, 0.6, 0.1, 0.8],
            "вдохновение": [0.3, 0.7, 0.5, 0.2, 0.8, 0.6, 0.1, 0.4, 0.3, 0.5, 0.7, 0.4, 0.2, 0.6, 0.1, 0.8],
            "inspiration": [0.3, 0.7, 0.5, 0.2, 0.8, 0.6, 0.1, 0.4, 0.3, 0.5, 0.7, 0.4, 0.2, 0.6, 0.1, 0.8]
        }
        desc_lower = description.lower()
        for emotion, vec in emotion_vectors.items():
            if emotion in desc_lower:
                return vec
        return [0.0] * 16

    # ═══════════════════════════════════════════════════════════
    # Rule-based методы (fallback)
    # ═══════════════════════════════════════════════════════════

    def _extract_intent(self, text: str) -> str:
        text_lower = text.lower()
        question_markers = ['?', '？', 'почему', 'как', 'что', 'где', 'когда',
                            'why', 'how', 'what', 'where', 'when', '为什么', '怎么', '什么', '哪里']
        if any(marker in text_lower for marker in question_markers):
            return "question"
        request_markers = ['пожалуйста', 'прошу', 'сделай', 'помоги',
                           'please', 'request', 'help', '请', '帮']
        if any(marker in text_lower for marker in request_markers):
            return "request"
        emotion_markers = ['чувствую', 'рад', 'грустно', 'счастлив',
                           'feel', 'happy', 'sad', 'love', '感觉', '开心', '难过']
        if any(marker in text_lower for marker in emotion_markers):
            return "emotion"
        return "statement"

    def _extract_domain(self, text: str) -> str:
        text_lower = text.lower()
        domains = {
            "science": ["наука", "физика", "математика", "химия",
                        "science", "physics", "math", "科学", "物理", "数学"],
            "technology": ["код", "программа", "алгоритм", "компьютер",
                           "code", "program", "algorithm", "代码", "程序", "算法"],
            "emotion": ["чувство", "эмоция", "любовь", "радость",
                        "feeling", "emotion", "love", "感情", "感觉", "爱"],
            "philosophy": ["смысл", "бытие", "сознание", "душа",
                           "meaning", "being", "consciousness", "意义", "存在", "意识"]
        }
        for domain, markers in domains.items():
            if any(marker in text_lower for marker in markers):
                return domain
        return "general"

    def _estimate_complexity(self, text: str) -> float:
        words = text.split()
        if not words:
            return 0.1
        avg_word_length = sum(len(w) for w in words) / len(words)
        unique_words = len(set(words)) / len(words)
        return min(1.0, (avg_word_length / 15 + unique_words) / 2)

    def _estimate_urgency(self, text: str) -> float:
        urgent_markers = [
            'срочно', 'немедленно', 'сейчас', 'быстро',
            'urgent', 'immediately', 'now', 'asap', '紧急', '立刻', '马上'
        ]
        return min(1.0, sum(1 for m in urgent_markers if m in text.lower()) * 0.3)

    def _analyze_code(self, code: str) -> Dict:
        return {
            "functions": len(re.findall(r'def |function |func ', code)),
            "classes": len(re.findall(r'class ', code)),
            "loops": len(re.findall(r'for |while ', code)),
            "conditionals": len(re.findall(r'if |else |elif |switch ', code)),
            "imports": len(re.findall(r'import |require |include ', code)),
            "complexity": (code.count('(') + code.count('{')) / max(len(code.split('\n')), 1)
        }

    def _extract_code_intent(self, structure: Dict) -> str:
        if structure["functions"] > 5:
            return "organize_logic"
        elif structure["loops"] > 3:
            return "process_data"
        elif structure["conditionals"] > 3:
            return "make_decisions"
        return "express_algorithm"
