"""
AEON Embedding Engine — реальные кросс-языковые эмбеддинги.
LaBSE: Language-agnostic BERT Sentence Embedding (768 dims, 109 языков).
Одно смысловое пространство для всех языков.
"""

import hashlib
import time
from typing import List, Dict, Optional, Tuple
import numpy as np

_SENTENCE_TRANSFORMERS = False
try:
    from sentence_transformers import SentenceTransformer
    _SENTENCE_TRANSFORMERS = True
except ImportError:
    pass


class EmbeddingEngine:
    """
    Кросс-языковой движок эмбеддингов.
    По умолчанию: paraphrase-multilingual-MiniLM-L12-v2 (384D, 50+ языков).
    Альтернатива: LaBSE (768D, 109 языков).
    """

    MODELS = {
        "multilingual_mini": "paraphrase-multilingual-MiniLM-L12-v2",
        "labse": "sentence-transformers/LaBSE",
        "distiluse": "distiluse-base-multilingual-cased-v2"
    }

    def __init__(self, model_name: str = "multilingual_mini"):
        self.model_name = model_name
        self.model_id = self.MODELS.get(model_name, model_name)
        self._model: Optional[SentenceTransformer] = None
        self.available = _SENTENCE_TRANSFORMERS
        self.dim = 768 if model_name == "labse" else 384
        self._cache: Dict[str, np.ndarray] = {}
        self._load_time = 0.0

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def load(self) -> 'EmbeddingEngine':
        """Загружает модель (при первом вызове — ~1.7 ГБ)."""
        if self._model is not None or not self.available:
            return self
        t0 = time.time()
        print(f"   Загрузка {self.model_id}...")
        self._model = SentenceTransformer(self.model_id)
        self._load_time = time.time() - t0
        print(f"   Готово за {self._load_time:.1f}с. Размерность: {self.dim}")
        return self

    def encode(self, text: str, use_cache: bool = True) -> np.ndarray:
        """
        Преобразует текст в 768-мерный вектор.
        Один и тот же смысл на разных языках → близкие векторы.
        """
        if not self.available:
            return np.zeros(self.dim, dtype=np.float32)

        cache_key = hashlib.sha256(text.encode()).hexdigest()
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        self.load()
        vec = self._model.encode(text, normalize_embeddings=True)
        if use_cache:
            self._cache[cache_key] = vec
        return vec

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """Пакетное кодирование."""
        if not self.available:
            return np.zeros((len(texts), self.dim), dtype=np.float32)
        self.load()
        return self._model.encode(texts, normalize_embeddings=True)

    def similarity(self, text_a: str, text_b: str) -> float:
        """Косинусное сходство двух текстов (0-1)."""
        if not self.available:
            return 0.5
        a = self.encode(text_a)
        b = self.encode(text_b)
        return float(np.dot(a, b))

    def cross_lingual_similarity(self, text_a: str, lang_a: str,
                                  text_b: str, lang_b: str) -> float:
        """
        Кросс-языковое сходство — ключевая метрика AEON.
        "Hello" vs "Привет" → ~0.95
        """
        return self.similarity(text_a, text_b)

    def align_score(self, text: str, reference_text: str) -> Tuple[float, str]:
        """
        Оценка кросс-языкового выравнивания.
        Возвращает (score, интерпретация).
        """
        sim = self.similarity(text, reference_text)
        if sim >= 0.85:
            return sim, "perfect_alignment"
        elif sim >= 0.65:
            return sim, "good_alignment"
        elif sim >= 0.45:
            return sim, "partial_alignment"
        else:
            return sim, "misaligned"

    def find_closest(self, query: str, candidates: List[str], top_k: int = 5) -> List[Tuple[str, float]]:
        """Поиск ближайших по смыслу среди кандидатов."""
        if not candidates:
            return []
        q_vec = self.encode(query)
        c_vecs = self.encode_batch(candidates)
        scores = np.dot(c_vecs, q_vec)
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

    def stats(self) -> dict:
        return {
            "model": self.model_id,
            "dimension": self.dim,
            "loaded": self.loaded,
            "load_time_sec": self._load_time,
            "cache_entries": len(self._cache),
            "available": self.available
        }


# Глобальный синглтон (ленивая загрузка)
_global_engine: Optional[EmbeddingEngine] = None


def get_embedding_engine(model: str = "multilingual_mini") -> EmbeddingEngine:
    global _global_engine
    if _global_engine is None:
        _global_engine = EmbeddingEngine(model)
    return _global_engine
