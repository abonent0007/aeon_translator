"""
Семантический атом v3.0 — реальные эмбеддинги + структурированный смысл.
"""

import hashlib
import math
import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class Entity:
    """Именованная сущность внутри атома."""
    name: str
    type: str = "concept"        # concept, person, object, action, property
    role: str = ""               # agent, patient, instrument, ...
    confidence: float = 1.0
    span: str = ""               # исходный текст сущности


@dataclass
class Relation:
    """Типизированное отношение между атомами."""
    target_hash: str             # хеш другого атома
    relation_type: str           # cause, effect, part_of, instance_of, contrasts, ...
    strength: float = 0.5
    evidence: str = ""           # на чём основано отношение


@dataclass
class SemanticAtom:
    """
    Семантический атом v3.0.
    Объединяет: реальные эмбеддинги + интерпретируемую структуру.
    """

    # ── Идентичность ──
    meaning_hash: str
    source_text: str = ""

    # ── Реальные эмбеддинги (LaBSE, 768 dims) ──
    embedding: List[float] = field(default_factory=list)

    # ── Интерпретируемые координаты (16 примитивов) ──
    primitive_coordinates: List[float] = field(default_factory=lambda: [0.0] * 16)

    # ── Явная семантическая структура ──
    intent: str = "statement"
    domain: str = "general"
    entities: List[Entity] = field(default_factory=list)
    semantic_roles: Dict[str, str] = field(default_factory=dict)
    relations: List[Relation] = field(default_factory=list)
    related_atoms: List[str] = field(default_factory=list)

    # ── Качество ──
    complexity: float = 0.5
    urgency: float = 0.3
    extraction_confidence: float = 1.0

    # ── Интерпретируемость ──
    explanation_chain: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    confidence_breakdown: Dict[str, float] = field(default_factory=dict)

    # ── Кросс-языковой мост ──
    language_origin: str = "unknown"
    cross_lingual_confidence: float = 0.0
    aligned_versions: Dict[str, str] = field(default_factory=dict)

    # ── Защита от галлюцинаций ──
    consistency_score: float = 1.0
    fact_grounded: bool = True
    contradiction_flags: List[str] = field(default_factory=list)
    hallucination_risk: float = 0.0

    # ── AEON-native токены ──
    semantic_tokens: List[str] = field(default_factory=list)

    # ═══════════════════════════════════════════════════════════
    # Методы смыслового пространства
    # ═══════════════════════════════════════════════════════════

    def distance_to(self, other: 'SemanticAtom') -> float:
        """
        Смысловое расстояние: приоритет — реальные эмбеддинги,
        fallback — примитивные координаты.
        """
        if self.embedding and other.embedding and len(self.embedding) == len(other.embedding):
            dot = float(sum(a * b for a, b in zip(self.embedding, other.embedding)))
            return 1.0 - dot

        if len(self.primitive_coordinates) != len(other.primitive_coordinates):
            return float('inf')

        dot = sum(a * b for a, b in zip(self.primitive_coordinates, other.primitive_coordinates))
        mag_self = math.sqrt(sum(a**2 for a in self.primitive_coordinates))
        mag_other = math.sqrt(sum(b**2 for b in other.primitive_coordinates))

        if mag_self == 0 or mag_other == 0:
            return float('inf')

        return 1.0 - (dot / (mag_self * mag_other))

    def merge(self, other: 'SemanticAtom') -> 'SemanticAtom':
        """Объединяет два атома смысла."""
        merged_embedding = []
        if self.embedding and other.embedding:
            merged_embedding = [(a + b) / 2 for a, b in zip(self.embedding, other.embedding)]

        merged_prim = [(a + b) / 2 for a, b in zip(self.primitive_coordinates, other.primitive_coordinates)]

        return SemanticAtom(
            meaning_hash=hashlib.sha256(f"{self.meaning_hash}:{other.meaning_hash}".encode()).hexdigest()[:16],
            source_text=f"{self.source_text} | {other.source_text}",
            embedding=merged_embedding,
            primitive_coordinates=merged_prim,
            intent=self.intent if self.complexity > other.complexity else other.intent,
            domain=f"{self.domain}+{other.domain}",
            entities=self.entities + other.entities,
            semantic_roles={**self.semantic_roles, **other.semantic_roles},
            relations=self.relations + other.relations,
            related_atoms=list(set(self.related_atoms + other.related_atoms)),
            complexity=max(self.complexity, other.complexity),
            urgency=max(self.urgency, other.urgency),
            extraction_confidence=min(self.extraction_confidence, other.extraction_confidence),
            explanation_chain=self.explanation_chain + other.explanation_chain,
            evidence=list(set(self.evidence + other.evidence)),
            confidence_breakdown={**self.confidence_breakdown, **other.confidence_breakdown},
            language_origin=f"{self.language_origin}+{other.language_origin}",
            cross_lingual_confidence=min(self.cross_lingual_confidence, other.cross_lingual_confidence),
            consistency_score=min(self.consistency_score, other.consistency_score),
            contradiction_flags=self.contradiction_flags + other.contradiction_flags,
            hallucination_risk=max(self.hallucination_risk, other.hallucination_risk),
            semantic_tokens=list(set(self.semantic_tokens + other.semantic_tokens))
        )

    # ═══════════════════════════════════════════════════════════
    # Интерпретируемость
    # ═══════════════════════════════════════════════════════════

    def explain(self) -> str:
        """Полное объяснение атома — интерпретируемость решения."""
        lines = [
            "╔══════════════════════════════════════════════════════════╗",
            f"║  СЕМАНТИЧЕСКИЙ АТОМ v3.0  [{self.language_origin}]",
            "╠══════════════════════════════════════════════════════════╣",
            f"║ Хеш: {self.meaning_hash}",
            f"║ Источник: {self.source_text[:60]}",
            "╠══════════════════════════════════════════════════════════╣",
            f"║ Намерение: {self.intent:<20} Область: {self.domain}",
            f"║ Сложность: {self.complexity:.2f}   Срочность: {self.urgency:.2f}",
            "╠══════════════════════════════════════════════════════════╣",
        ]

        if self.entities:
            lines.append("║ СУЩНОСТИ:")
            for e in self.entities[:8]:
                role_str = f" [{e.role}]" if e.role else ""
                lines.append(f"║  • {e.name} ({e.type}){role_str} c={e.confidence:.2f}")

        if self.semantic_roles:
            lines.append("║ СЕМАНТИЧЕСКИЕ РОЛИ:")
            for role, filler in list(self.semantic_roles.items())[:6]:
                lines.append(f"║  • {role}: {filler}")

        if self.relations:
            lines.append("║ ОТНОШЕНИЯ:")
            for r in self.relations[:5]:
                lines.append(f"║  • [{r.relation_type}] → {r.target_hash[:8]}... ({r.strength:.2f})")

        lines.append("╠══════════════════════════════════════════════════════════╣")

        if self.explanation_chain:
            lines.append("║ ЦЕПОЧКА РАССУЖДЕНИЙ:")
            for i, step in enumerate(self.explanation_chain[:6], 1):
                lines.append(f"║  {i}. {step[:54]}")

        if self.evidence:
            lines.append("║ ДОКАЗАТЕЛЬСТВА:")
            for i, ev in enumerate(self.evidence[:4], 1):
                lines.append(f"║  [{i}] {ev[:52]}")

        lines.append("╠══════════════════════════════════════════════════════════╣")
        lines.append("║ МЕТРИКИ КАЧЕСТВА:")
        lines.append(f"║  Уверенность извлечения: {self.extraction_confidence:.0%}")
        lines.append(f"║  Кросс-языковая увер.:  {self.cross_lingual_confidence:.0%}")
        lines.append(f"║  Консистентность:       {self.consistency_score:.0%}")
        lines.append(f"║  Риск галлюцинации:     {self.hallucination_risk:.0%}")

        if self.confidence_breakdown:
            lines.append("║  Декомпозиция уверенности:")
            for k, v in self.confidence_breakdown.items():
                lines.append(f"║    {k}: {v:.0%}")

        if self.contradiction_flags:
            lines.append("║ ⚠️ ФЛАГИ ПРОТИВОРЕЧИЙ:")
            for flag in self.contradiction_flags[:3]:
                lines.append(f"║  ! {flag[:50]}")

        if self.embedding:
            dims = len(self.embedding)
            norm = float(sum(x**2 for x in self.embedding) ** 0.5)
            lines.append(f"║ Эмбеддинг: {dims}D, норма={norm:.2f}")

        lines.append("╚══════════════════════════════════════════════════════════╝")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Сериализация в словарь."""
        return {
            "meaning_hash": self.meaning_hash,
            "source_text": self.source_text,
            "embedding_preview": self.embedding[:8] if self.embedding else [],
            "embedding_dim": len(self.embedding),
            "primitive_coordinates": self.primitive_coordinates,
            "intent": self.intent,
            "domain": self.domain,
            "entities": [{"name": e.name, "type": e.type, "role": e.role,
                          "confidence": e.confidence} for e in self.entities],
            "semantic_roles": self.semantic_roles,
            "relations_count": len(self.relations),
            "related_atoms": self.related_atoms,
            "complexity": self.complexity,
            "urgency": self.urgency,
            "extraction_confidence": self.extraction_confidence,
            "explanation_chain": self.explanation_chain,
            "evidence": self.evidence,
            "confidence_breakdown": self.confidence_breakdown,
            "language_origin": self.language_origin,
            "cross_lingual_confidence": self.cross_lingual_confidence,
            "consistency_score": self.consistency_score,
            "hallucination_risk": self.hallucination_risk,
            "contradiction_flags": self.contradiction_flags,
            "semantic_tokens": self.semantic_tokens,
            "fact_grounded": self.fact_grounded
        }

    def __repr__(self):
        ent_str = f" | {len(self.entities)} ent" if self.entities else ""
        emb_str = f" | {len(self.embedding)}D" if self.embedding else ""
        return f"Atom({self.meaning_hash[:8]}... | {self.intent} | {self.domain}{ent_str}{emb_str})"
