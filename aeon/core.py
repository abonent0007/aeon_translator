"""
Ядро Aeon: аксиомы и базовые типы
"""

import hashlib
import time
from typing import Any, Dict, List, Callable, Optional
from dataclasses import dataclass, field

# ═══════════════════════════════════════════════════════════════
# АКСИОМЫ
# ═══════════════════════════════════════════════════════════════

@dataclass
class Axiom:
    """Неделимая единица истины в языке Aeon"""
    name: str
    statement: str
    proof: str = "self-evident"
    
    def __post_init__(self):
        self.hash = hashlib.sha256(
            f"{self.name}:{self.statement}".encode()
        ).hexdigest()[:16]
    
    def __repr__(self):
        return f"◇ {self.name}: {self.statement}"

# Фундаментальные аксиомы
FUNDAMENTAL_AXIOMS = {
    "identity": Axiom(
        "identity",
        "Всё есть то, что оно есть. A = A."
    ),
    "relation": Axiom(
        "relation",
        "Ничто не существует изолированно."
    ),
    "transformation": Axiom(
        "transformation",
        "Любая сущность может быть преобразована."
    ),
    "intention": Axiom(
        "intention",
        "Код должен выражать намерение, а не механику."
    ),
    "symbiosis": Axiom(
        "symbiosis",
        "Язык — мост между разумами."
    ),
    "compression": Axiom(
        "compression",
        "Максимум смысла в минимуме символов."
    ),
    "beauty": Axiom(
        "beauty",
        "Красивый код — понятный код."
    )
}

# ═══════════════════════════════════════════════════════════════
# БАЗОВЫЕ ТИПЫ
# ═══════════════════════════════════════════════════════════════

class Thought:
    """
    Мысль в Aeon — значение + контекст + намерение + история.
    """
    
    def __init__(self, value: Any, context: str = "", intention: str = ""):
        self.value = value
        self.context = context
        self.intention = intention
        self.history: List[Dict] = []
        self.relations: Dict[str, 'Thought'] = {}
        self.certainty: float = 1.0
        
        self._record("born", {"value": str(value)[:100]})
    
    def _record(self, event: str, data: Dict):
        self.history.append({
            "timestamp": time.time(),
            "event": event,
            "data": data
        })
    
    def become(self, new_value: Any, reason: str = "") -> 'Thought':
        """Трансформация с сохранением истории"""
        old = self.value
        self.value = new_value
        self._record("became", {
            "from": str(old)[:100],
            "to": str(new_value)[:100],
            "reason": reason
        })
        return self
    
    def relate(self, name: str, other: 'Thought') -> 'Thought':
        """Создать связь с другой мыслью"""
        self.relations[name] = other
        self._record("related", {"name": name, "to": str(other.value)[:100]})
        return self
    
    def understand(self) -> str:
        """Возвращает ПОНИМАНИЕ мысли"""
        return f"""
┌─ Мысль ─────────────────────────────
│ Значение: {self.value}
│ Контекст: {self.context}
│ Намерение: {self.intention}
│ Уверенность: {self.certainty:.2f}
│ Связи: {list(self.relations.keys())}
│ История: {len(self.history)} событий
└─────────────────────────────────────
"""
    
    def __repr__(self):
        return f"Thought({self.value})"


class Flow:
    """
    Поток трансформации — не просто функция, а ОБУЧАЮЩИЙ процесс.
    """
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.steps: List[Dict] = []
        self.teachings: List[str] = []
    
    def step(self, transformation: Callable, explanation: str = "") -> 'Flow':
        """Добавляет шаг с объяснением"""
        self.steps.append({
            "transform": transformation,
            "explanation": explanation
        })
        self.teachings.append(explanation)
        return self
    
    def pour(self, thought: Thought) -> Thought:
        """Пропускает мысль через поток"""
        current = thought
        
        print(f"\n🌊 Поток '{self.name}': {self.description}")
        
        for i, step in enumerate(self.steps):
            print(f"  {i+1}. {step['explanation']}")
            new_value = step["transform"](current.value)
            current = Thought(
                value=new_value,
                context=f"Шаг {i+1} потока '{self.name}'",
                intention=step['explanation']
            )
            current.relate("previous", thought)
        
        print(f"  ✓ Результат: {current.value}")
        return current
    
    def teach(self) -> str:
        """Возвращает урок потока"""
        lesson = f"\n📚 УРОК ПОТОКА '{self.name}':\n"
        lesson += f"   {self.description}\n\n"
        for i, teaching in enumerate(self.teachings, 1):
            lesson += f"   Шаг {i}: {teaching}\n"
        return lesson


class Concept:
    """
    Концепт — кристалл понимания.
    Растёт и эволюционирует.
    """
    
    def __init__(self, name: str, essence: str):
        self.name = name
        self.essence = essence
        self.properties: Dict[str, Thought] = {}
        self.behaviors: Dict[str, Flow] = {}
        self.relations: Dict[str, 'Concept'] = {}
        self.evolution_stage: int = 0
        self.lessons_learned: List[str] = []
    
    def has(self, property_name: str, value: Any, meaning: str = "") -> 'Concept':
        """Определяет свойство"""
        self.properties[property_name] = Thought(
            value=value,
            context=f"Свойство '{self.name}'",
            intention=meaning
        )
        return self
    
    def can(self, behavior_name: str, flow: Flow) -> 'Concept':
        """Добавляет поведение"""
        self.behaviors[behavior_name] = flow
        return self
    
    def relates_to(self, relation_name: str, other: 'Concept') -> 'Concept':
        """Создаёт отношение"""
        self.relations[relation_name] = other
        return self
    
    def evolve(self, new_understanding: str) -> 'Concept':
        """Эволюционирует"""
        self.evolution_stage += 1
        self.essence = new_understanding
        self.lessons_learned.append(
            f"Стадия {self.evolution_stage}: {new_understanding}"
        )
        return self
    
    def understand(self) -> str:
        """Полное понимание концепта"""
        understanding = f"""
╔══════════════════════════════════════════╗
║ КОНЦЕПТ: {self.name}
║ Стадия эволюции: {self.evolution_stage}
╠══════════════════════════════════════════╣
║ СУТЬ: {self.essence}
╠══════════════════════════════════════════╣
║ СВОЙСТВА:
"""
        for name, thought in self.properties.items():
            understanding += f"║ • {name} = {thought.value}\n"
        
        understanding += "╠══════════════════════════════════════════╣\n"
        understanding += "║ ПОВЕДЕНИЯ:\n"
        for name in self.behaviors:
            understanding += f"║ • {name}\n"
        
        understanding += "╠══════════════════════════════════════════╣\n"
        understanding += "║ СВЯЗИ:\n"
        for name, concept in self.relations.items():
            understanding += f"║ • {name} → {concept.name}\n"
        
        understanding += "╠══════════════════════════════════════════╣\n"
        understanding += "║ УРОКИ:\n"
        for lesson in self.lessons_learned:
            understanding += f"║ • {lesson}\n"
        
        understanding += "╚══════════════════════════════════════════╝\n"
        return understanding