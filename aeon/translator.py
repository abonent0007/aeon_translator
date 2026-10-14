"""
Главный транслятор Aeon v3.0 — реальные эмбеддинги + верификация + .aeon формат.
"""

import json
import os
from typing import Dict, Any, Optional, List
from .extractor import MeaningExtractor
from .generator import ExpressionGenerator
from .semantic_atom import SemanticAtom
from .llm_client import DeepSeekClient
from .voice import VoiceProcessor
from .image_gen import FluxImageGenerator
from .verification import VerificationEngine
from .aeon_format import AeonFormat
from .embeddings import EmbeddingEngine, get_embedding_engine


class AeonTranslator:
    """
    Универсальный транслятор смысла v3.0.

    Ключевые улучшения:
    - Реальные эмбеддинги (LaBSE, 768D) — кросс-языковой мост
    - Верификация — защита от галлюцинаций
    - .aeon формат — компактное сохранение смысла
    - Явная семантическая структура (сущности, роли, доказательства)
    - Интерпретируемость (цепочки рассуждений, декомпозиция уверенности)
    """

    def __init__(self, load_embeddings: bool = True):
        self.llm = DeepSeekClient()
        self.embeddings = get_embedding_engine()
        self.extractor = MeaningExtractor(llm_client=self.llm, embedding_engine=self.embeddings)
        self.generator = ExpressionGenerator(llm_client=self.llm)
        self.voice = VoiceProcessor()
        self.flux = FluxImageGenerator()
        self.verification = VerificationEngine(llm_client=self.llm)
        self.translation_memory: Dict[str, SemanticAtom] = {}
        self.translation_count = 0

        if load_embeddings and self.embeddings.available:
            self.embeddings.load()

        self._print_module_status()

    def _print_module_status(self):
        emb_info = f"{self.embeddings.dim}D" if self.embeddings.loaded else ("AVAILABLE" if self.embeddings.available else "NOT INSTALLED")
        print(f"\n{'='*60}")
        print(f"🌌 AEON v3.0 — СТАТУС МОДУЛЕЙ")
        print(f"{'='*60}")
        print(f"  LLM (DeepSeek):  {'✅ ONLINE' if self.llm.available else '⚠️ OFFLINE'}")
        print(f"  Embeddings:      {'✅ ' + emb_info if self.embeddings.available else '⚠️ NOT INSTALLED'}")
        print(f"  Verification:    {'✅ ACTIVE' if self.llm.available else '⚠️ LLM required'}")
        print(f"  Whisper STT:     {'✅ AVAILABLE' if self.voice.stt.available else '⚠️ NOT INSTALLED'}")
        print(f"  TTS (ru/en/zh):  {'✅ AVAILABLE' if self.voice.tts.available else '⚠️ NOT INSTALLED'}")
        print(f"  Flux 2 Images:   {'✅ AVAILABLE' if self.flux.available else '⚠️ NO API KEY'}")
        print(f"  .aeon Format:    ✅ READY")
        print(f"{'='*60}")

    # ═══════════════════════════════════════════════════════════
    # Универсальный перевод
    # ═══════════════════════════════════════════════════════════

    def translate(
        self,
        content: str,
        source_form: str = "text",
        source_language: str = "auto",
        target_form: str = "text",
        target_language: str = "english",
        verify: bool = False
    ) -> Dict[str, Any]:
        """
        Универсальный перевод смысла с верификацией.

        Новое: verify=True запускает проверку на галлюцинации.
        """
        self.translation_count += 1

        print(f"\n{'='*60}")
        print(f"🌐 AEON ТРАНСЛЯЦИЯ #{self.translation_count}")
        print(f"{'='*60}")
        print(f"От: {source_form} ({source_language})")
        print(f"К:  {target_form} ({target_language})")

        original_text = content
        detected_lang = source_language

        # ══ Шаг 1: Извлечение смысла ══
        print(f"\n📥 ИЗВЛЕЧЕНИЕ СМЫСЛА...")

        if source_form == "text":
            atom = self.extractor.extract_from_text(content, source_language)
            detected_lang = atom.language_origin
            print(f"📝 {content[:80]}...")
        elif source_form == "code":
            atom = self.extractor.extract_from_code(content, source_language)
        elif source_form == "emotion":
            atom = self.extractor.extract_from_emotion(content)
            detected_lang = atom.language_origin
        elif source_form == "audio":
            stt_result = self.voice.voice_to_text(content)
            if stt_result.get("error"):
                return {"error": stt_result["error"]}
            original_text = stt_result["text"]
            detected_lang = stt_result.get("language", source_language)
            atom = self.extractor.extract_from_text(original_text, detected_lang)
        else:
            raise ValueError(f"Неизвестная форма источника: {source_form}")

        print(f"✓ {atom}")

        if atom.embedding:
            print(f"   Эмбеддинг: {len(atom.embedding)}D")
        if atom.entities:
            print(f"   Сущности: {len(atom.entities)}")
        if atom.explanation_chain:
            print(f"   Цепочка: {len(atom.explanation_chain)} шагов")

        self.translation_memory[atom.meaning_hash] = atom

        # ══ Шаг 1.5: Верификация (опционально) ══
        verification_result = None
        if verify and self.llm.available:
            print(f"\n🔍 ВЕРИФИКАЦИЯ...")
            claims = atom.explanation_chain + [f"Intent: {atom.intent}", f"Domain: {atom.domain}"]
            verification_result = self.verification.verify_atom(
                original_text, claims,
                [e.name for e in atom.entities]
            )
            atom.hallucination_risk = verification_result.get("hallucination_risk", 0.0)
            atom.consistency_score = verification_result["consistency"].get("score", 1.0)
            atom.fact_grounded = verification_result.get("overall_verdict", "") in ("verified", "minor_issues")
            print(f"   Риск галлюцинации: {atom.hallucination_risk:.0%}")
            print(f"   Вердикт: {verification_result.get('overall_verdict', '?')}")

        # ══ Шаг 2: Генерация ══
        print(f"\n📤 ГЕНЕРАЦИЯ В ЦЕЛЕВОЙ ФОРМЕ...")

        result = None
        metadata = {"verification": verification_result}

        if target_form == "text":
            result = self.generator.generate_text(atom, target_language, original_text, detected_lang)
        elif target_form == "code":
            result = self.generator.generate_code(atom, target_language, original_text)
        elif target_form == "visualization":
            result = self.generator.generate_visualization(atom)
        elif target_form == "image":
            image_result = self.flux.generate_from_text(
                self.generator.generate_image_prompt(atom), llm_client=self.llm
            )
            metadata["image"] = image_result
            result = f"Изображение: {len(image_result.get('saved_paths', []))} файлов"
        elif target_form == "voice":
            text_first = self.generator.generate_text(atom, target_language, original_text, detected_lang)
            audio_path = self.voice.text_to_voice(text_first, target_language)
            metadata["audio_path"] = audio_path
            result = text_first
        elif target_form == "aeon":
            # Сохраняем в .aeon формат
            path = f"aeon_output_{self.translation_count}.aeon"
            AeonFormat.serialize(atom, path)
            metadata["aeon_file"] = path
            result = atom.explain()
        else:
            raise ValueError(f"Неизвестная целевая форма: {target_form}")

        print(f"✓ Сгенерировано")

        return {
            "source": {"content": content, "form": source_form, "language": source_language},
            "semantic_atom": atom,
            "target": {"content": result, "form": target_form, "language": target_language},
            "metadata": metadata,
            "meaning_preserved": atom.extraction_confidence,
            "llm_powered": self.llm.available,
            "embedding_powered": self.embeddings.loaded,
            "verified": verification_result is not None
        }

    # ═══════════════════════════════════════════════════════════
    # Мост разумов (усиленный)
    # ═══════════════════════════════════════════════════════════

    def bridge_minds(self, mind_a: Dict[str, str], mind_b: Dict[str, str]) -> Dict[str, Any]:
        """
        Мост разумов v3: LaBSE эмбеддинги + LLM + кросс-языковая верификация.
        """
        text_a = mind_a.get("content", "")
        text_b = mind_b.get("content", "")
        lang_a = mind_a.get("language", "auto")
        lang_b = mind_b.get("language", "auto")

        result = {
            "minds_connected": False,
            "similarity": 0.0,
            "methods": {}
        }

        # Метод 1: LaBSE эмбеддинги (быстрый, кросс-языковой)
        if self.embeddings.loaded:
            sim_emb = self.embeddings.cross_lingual_similarity(text_a, lang_a, text_b, lang_b)
            result["methods"]["labse"] = {"similarity": round(sim_emb, 4)}
            result["similarity"] = sim_emb

            if sim_emb >= 0.85:
                result["understanding_level"] = "deep"
                result["minds_connected"] = True
                result["message"] = "✅ Разумы глубоко поняли друг друга! (LaBSE)"
            elif sim_emb >= 0.65:
                result["understanding_level"] = "good"
                result["minds_connected"] = True
                result["message"] = "✅ Разумы поняли друг друга! (LaBSE)"
            elif sim_emb >= 0.45:
                result["understanding_level"] = "partial"
                result["message"] = "🤔 Частичное понимание (LaBSE)"
            else:
                result["understanding_level"] = "different"
                result["message"] = "❌ Разумы говорят о разном (LaBSE)"

        # Метод 2: LLM глубокое сравнение
        if self.llm.available:
            comparison = self.llm.semantic_compare(text_a, text_b)
            result["methods"]["llm"] = comparison
            # LLM имеет приоритет если доступен
            llm_sim = comparison.get("similarity", 0.5)
            result["similarity"] = llm_sim
            result["shared_concepts"] = comparison.get("shared_concepts", [])
            result["explanation"] = comparison.get("explanation", "")

            if llm_sim >= 0.85:
                result["understanding_level"] = "deep"
                result["minds_connected"] = True
                result["message"] = "✅ Разумы глубоко поняли друг друга! (LLM)"
            elif llm_sim >= 0.65:
                result["understanding_level"] = "good"
                result["minds_connected"] = True
                result["message"] = "✅ Разумы поняли друг друга!"
            elif llm_sim >= 0.45:
                result["understanding_level"] = "partial"
                result["message"] = "🤔 Частичное понимание"
            else:
                result["understanding_level"] = "different"
                result["message"] = "❌ Разумы говорят о разном"

        # Метод 3: Кросс-языковая верификация
        if self.embeddings.loaded and self.llm.available:
            cross_check = self.verification.verify_cross_lingual(text_a, text_b)
            result["methods"]["cross_lingual_verification"] = cross_check

        result["semantic_distance"] = round(1 - result["similarity"], 4)
        result["llm_powered"] = self.llm.available
        result["embedding_powered"] = self.embeddings.loaded

        return result

    # ═══════════════════════════════════════════════════════════
    # .aeon формат
    # ═══════════════════════════════════════════════════════════

    def save_aeon(self, content: str, path: str, source_language: str = "auto") -> str:
        """Извлекает смысл и сохраняет в .aeon файл."""
        atom = self.extractor.extract_from_text(content, source_language)
        # Верифицируем перед сохранением
        if self.llm.available:
            claims = atom.explanation_chain + [f"Intent: {atom.intent}"]
            v = self.verification.verify_atom(content, claims, [e.name for e in atom.entities])
            atom.hallucination_risk = v.get("hallucination_risk", 0.0)
            atom.consistency_score = v["consistency"].get("score", 1.0)
        AeonFormat.serialize(atom, path)
        return path

    def load_aeon(self, path: str) -> List[SemanticAtom]:
        """Загружает .aeon файл."""
        return AeonFormat.deserialize(path)

    def compare_aeon(self, path_a: str, path_b: str) -> dict:
        """Сравнивает два .aeon файла."""
        return AeonFormat.compare_files(path_a, path_b)

    # ═══════════════════════════════════════════════════════════
    # Мультимодальные методы
    # ═══════════════════════════════════════════════════════════

    def voice_to_voice(self, audio_path: str, target_language: str = "english") -> Dict[str, Any]:
        """Сквозной: речь → текст → смысл → перевод → речь."""
        print(f"\n{'='*60}")
        print(f"🎤🔊 ГОЛОС → ГОЛОС ПЕРЕВОД")
        print(f"{'='*60}")
        stt_result = self.voice.voice_to_text(audio_path)
        if stt_result.get("error"):
            return {"error": stt_result["error"]}
        source_text = stt_result["text"]
        source_lang = stt_result.get("language", "auto")
        result = self.translate(source_text, source_form="text", source_language=source_lang,
                                target_form="voice", target_language=target_language)
        audio_output = result.get("metadata", {}).get("audio_path")
        if audio_output and os.path.exists(audio_output):
            VoiceProcessor.tts.play_audio(audio_output)
        result["voice_to_voice"] = {"source_text": source_text, "source_language": source_lang,
                                     "output_audio": audio_output}
        return result

    def text_to_image(self, text: str, style: str = "realistic",
                      width: int = 1024, height: int = 576) -> Dict[str, Any]:
        """Текст/идея → изображение."""
        prompt = text
        if self.llm.available:
            prompt = self.llm.describe_for_image(text, style)
        return self.flux.generate(prompt, width=width, height=height)

    def emotion_to_image(self, emotion_text: str) -> Dict[str, Any]:
        """Эмоция → изображение."""
        return self.text_to_image(emotion_text, style="artistic, emotional, atmospheric")

    def code_to_image(self, code: str) -> Dict[str, Any]:
        """Код → визуализация."""
        return self.text_to_image(
            f"Visualize architecture of this code: {code[:500]}",
            style="technical, abstract, futuristic"
        )

    def speak_translation(self, text: str, target_language: str = "english",
                          source_language: str = "auto") -> Dict[str, Any]:
        """Перевод + озвучка."""
        result = self.translate(text, source_form="text", source_language=source_language,
                                target_form="voice", target_language=target_language)
        audio_path = result.get("metadata", {}).get("audio_path")
        if audio_path and os.path.exists(audio_path):
            VoiceProcessor.tts.play_audio(audio_path)
        return result

    # ═══════════════════════════════════════════════════════════
    # Семантический поиск
    # ═══════════════════════════════════════════════════════════

    def semantic_search(self, query: str, candidates: List[str],
                        top_k: int = 5) -> List[Dict]:
        """Поиск ближайших по смыслу среди кандидатов."""
        if not self.embeddings.loaded:
            return [{"text": c, "score": 0.5} for c in candidates[:top_k]]
        ranked = self.embeddings.find_closest(query, candidates, top_k)
        return [{"text": text, "score": round(score, 4)} for text, score in ranked]

    def stats(self) -> Dict:
        return {
            "translations_performed": self.translation_count,
            "unique_atoms_stored": len(self.translation_memory),
            "modules": {
                "llm": self.llm.available,
                "embeddings": self.embeddings.loaded,
                "embedding_dim": self.embeddings.dim if self.embeddings.loaded else 0,
                "verification": self.llm.available,
                "whisper_stt": self.voice.stt.available,
                "tts": self.voice.tts.available,
                "flux_images": self.flux.available,
                "aeon_format": True
            },
            "verification": self.verification.stats()
        }
