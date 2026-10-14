"""
Извлекатель смысла v3.0 — реальные эмбеддинги + структурированный смысл.
LLM-powered + LaBSE embeddings + entity extraction + роль labelling + explainability.
"""

import hashlib
import re
import json
from typing import List, Dict, Optional
import numpy as np
from .semantic_atom import (
    SemanticAtom,
    Entity,
    Relation,
    FRAGMENT_THRESHOLD,
    compute_completeness,
    detect_lacunae,
)
from .llm_client import DeepSeekClient
from .embeddings import EmbeddingEngine, get_embedding_engine
from .logging_config import get_logger, log_event
from .config import CONFIG
from .entity_linking import LinkResult, WikidataClient
from .crosswalk import PleiadesClient


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
                 embedding_engine: Optional[EmbeddingEngine] = None,
                 entity_linker: Optional[WikidataClient] = None,
                 pleiades_client: Optional[PleiadesClient] = None):
        self.llm = llm_client or DeepSeekClient()
        self.embeddings = embedding_engine or get_embedding_engine()
        self._entity_linker = entity_linker
        self._pleiades = pleiades_client

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

        # 6. Фрагменты: лакуна источника и качество извлечения — ортогональны
        completeness = compute_completeness(
            intent=structure.get("intent", "statement"),
            domain=structure.get("domain", "general"),
            entities=entities,
            semantic_roles=roles,
            evidence=evidence,
        )
        is_fragment = detect_lacunae(text)  # свойство источника
        needs_attention = is_fragment or completeness < FRAGMENT_THRESHOLD

        # 7. Entity Linking (опционально; enabled=False → 0 сетевых вызовов)
        self._link_entities(entities, detected_lang)
        for entity in entities:
            entity.is_fragment = is_fragment
            entity.completeness_score = completeness

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
            semantic_tokens=tokens,
            is_fragment=is_fragment,
            completeness_score=completeness,
            needs_attention=needs_attention,
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

        prompt = f"""Analyze the following text and return a semantic structure as ONLY valid JSON (no markdown).

TEXT: "{text}"
LANGUAGE: {language}

CONTRACT RULES:
1. entities are NAMED REFERENTS only.
   INCLUDE: personal names, deities, groups/tribes, places, objects, abstract entities (rare).
   EXCLUDE: pronouns, common nouns, adjectives, verbs, descriptions, translations.
   name: minimal named form exactly as in the source (no articles: Ἀθηναίων, not ὁ Ἀθηναίων;
   no patronymic phrases: Ἀχιλῆος, not Πηληϊάδεω Ἀχιλῆος).
   type: person | deity | group | place | object | abstract — all six are equally valid
   (place and object are common in geographic, dedicatory and material texts).
   role: agent | patient | instrument | location | time | manner | goal — thematic role in the
   clause; semantic_roles may also reference non-entity constituents (common nouns, pronouns).
2. Language enforcement: entity names and evidence MUST be in the SOURCE language — never
   translated. If unsure of the source form, use name: null instead of a translation.
3. explanation_chain: 1-5 working analytical claims IN ENGLISH — this is NOT a translation and
   must NOT be cited as source. Each claim MUST contain at least one verbatim anchor from the
   TEXT; every anchor must be a substring of one of the evidence quotes.
4. evidence: 1-4 NON-redundant exact quotes (no quote is a substring of another); for a short
   segment one full quote is valid.
5. entities[].role and semantic_roles are inverse views; keep them consistent when both given.

Return a JSON object with these fields:
- "intent": one of [question, request, emotion, statement, command, declaration]
- "domain": one of [science, technology, emotion, philosophy, general, art, business, politics,
  literature, history, epigraphy, papyrology, religion]
- "entities": list of objects with {{"name", "type", "role", "span"}} per CONTRACT RULE 1
- "semantic_roles": object with keys [agent, patient, instrument, location, time, goal, manner]
- "semantic_primitives": list from [existence, action, relation, property, quantity, quality,
  time, space, cause, effect, purpose, means, part, whole, similarity, difference]
- "evidence": per CONTRACT RULE 4
- "explanation_chain": per CONTRACT RULE 3
- "confidence_breakdown": object with scores 0-1 for {{"intent", "domain", "entities", "roles"}}
- "complexity": float 0-1
- "urgency": float 0-1
- "extraction_confidence": float 0-1
- "semantic_tokens": list of 3-10 key concept tokens (English allowed)

--- Example 1 (Greek) ---
TEXT: "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ πλάγχθη"
{{"intent": "command", "domain": "literature",
 "entities": [{{"name": "Μοῦσα", "type": "deity", "role": "agent", "span": "Μοῦσα"}}],
 "semantic_roles": {{"agent": "Μοῦσα", "patient": "ἄνδρα", "instrument": "", "location": "",
                    "time": "", "goal": "μοι", "manner": ""}},
 "semantic_primitives": ["existence", "action", "relation", "purpose", "quantity"],
 "evidence": ["ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον", "ὃς μάλα πολλὰ πλάγχθη"],
 "explanation_chain": ["Narrator invokes the Muse to sing of a much-wandering man (ἔννεπε imperative).",
   "The Muse is the agent of the song; ἄνδρα is its subject, πολύτροπον his defining trait.",
   "The relative clause ὃς μάλα πολλὰ πλάγχθη defines the extent of his wandering."],
 "confidence_breakdown": {{"intent": 0.95, "domain": 0.9, "entities": 0.9, "roles": 0.8}},
 "complexity": 0.5, "urgency": 0.1, "extraction_confidence": 0.9,
 "semantic_tokens": ["invocation", "muse", "wandering", "hero"]}}

--- Example 2 (Latin) ---
TEXT: "Apud Helvētiōs longē nōbilissimus fuit et dītissimus Orgetorīx."
{{"intent": "statement", "domain": "history",
 "entities": [{{"name": "Helvētiōs", "type": "group", "role": "location", "span": "Helvētiōs"}},
              {{"name": "Orgetorīx", "type": "person", "role": "agent", "span": "Orgetorīx"}}],
 "semantic_roles": {{"agent": "Orgetorīx", "patient": "", "instrument": "", "location": "Helvētiōs",
                    "time": "", "goal": "", "manner": ""}},
 "semantic_primitives": ["existence", "property", "relation", "whole"],
 "evidence": ["Apud Helvētiōs longē nōbilissimus fuit et dītissimus Orgetorīx"],
 "explanation_chain": ["Orgetorix's superlative standing among the Helvetii is asserted through two coordinated superlatives (nōbilissimus, dītissimus, Orgetorīx).",
   "The superlatives mark his pre-eminence within that community (Helvētiōs)."],
 "confidence_breakdown": {{"intent": 0.95, "domain": 0.9, "entities": 0.9, "roles": 0.85}},
 "complexity": 0.3, "urgency": 0.1, "extraction_confidence": 0.9,
 "semantic_tokens": ["Helvetii", "Orgetorix", "nobility", "wealth"]}}

--- Example 3 (Greek, epigraphic register) ---
TEXT: "Ἀθηναῖοι ἀνέθεσαν τῷ Διὶ τρόπαιον ἐν Ὀλυμπίᾳ."
{{"intent": "statement", "domain": "epigraphy",
 "entities": [{{"name": "Ἀθηναῖοι", "type": "group", "role": "agent", "span": "Ἀθηναῖοι"}},
              {{"name": "Διὶ", "type": "deity", "role": "goal", "span": "Διὶ"}},
              {{"name": "τρόπαιον", "type": "object", "role": "patient", "span": "τρόπαιον"}},
              {{"name": "Ὀλυμπίᾳ", "type": "place", "role": "location", "span": "Ὀλυμπίᾳ"}}],
 "semantic_roles": {{"agent": "Ἀθηναῖοι", "patient": "τρόπαιον", "instrument": "",
                    "location": "Ὀλυμπίᾳ", "time": "", "goal": "Διὶ", "manner": ""}},
 "semantic_primitives": ["action", "relation", "purpose", "part"],
 "evidence": ["Ἀθηναῖοι ἀνέθεσαν τῷ Διὶ τρόπαιον ἐν Ὀλυμπίᾳ"],
 "explanation_chain": ["The inscription records a dedicatory act by the Athenians, addressed to Zeus and located at Olympia (ἀνέθεσαν, τῷ Διὶ, Ὀλυμπίᾳ).",
   "The dedication formula assigns the object (τρόπαιον) and the recipient deity (Διὶ)."],
 "confidence_breakdown": {{"intent": 0.9, "domain": 0.9, "entities": 0.9, "roles": 0.85}},
 "complexity": 0.3, "urgency": 0.1, "extraction_confidence": 0.9,
 "semantic_tokens": ["dedication", "trophy", "Zeus", "Olympia"]}}

Now analyze TEXT and return ONLY the JSON object."""

        result = self.llm._call_json([
            {"role": "system", "content": "You are a semantic structure analyzer. Return ONLY valid JSON. No markdown, no explanations outside JSON."},
            {"role": "user", "content": prompt}
        ], temperature=0.2, max_tokens=2000)

        if result.get("parse_error"):
            log_event(
                get_logger("aeon.extractor"),
                "extract_structure_parse_error",
                reason=result.get("parse_error"),
                trace_id=getattr(self.llm, "trace_id", None),
            )
            return self._extract_structure_rule(text, language)

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
    # Entity Linking (v4.0)
    # ═══════════════════════════════════════════════════════════

    WIKIDATA_LANGUAGES = {"english": "en", "russian": "ru", "chinese": "zh"}

    def _link_entities(self, entities: List[Entity], language: str) -> None:
        """Связывает сущности с Wikidata (+ Pleiades enrichment). Graceful."""
        if not entities:
            return

        linker = self._entity_linker
        if linker is None:
            if not CONFIG.entity_linking.enabled:
                return
            linker = WikidataClient()
            self._entity_linker = linker
            if self._pleiades is None:
                self._pleiades = PleiadesClient()

        wd_language = self.WIKIDATA_LANGUAGES.get(language, "en")
        limit = CONFIG.entity_linking.max_links_per_atom

        for entity in entities[:limit]:
            result: LinkResult = linker.link_mention(entity.name, language=wd_language)
            if result.source_unavailable:
                entity.source_unavailable = True
                continue
            if result.entity is None:
                continue

            entity.external_ids = dict(result.external_ids)
            entity.link_confidence = result.score

            pleiades_id = entity.external_ids.get("pleiades")
            if pleiades_id and self._pleiades is not None:
                place_result = self._pleiades.get_place(pleiades_id)
                if place_result.place is not None and place_result.place.title:
                    entity.external_labels["pleiades"] = place_result.place.title

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
