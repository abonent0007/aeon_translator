#!/usr/bin/env python3
"""
Демонстрация Aeon v2.0 — Универсального Транслятора Смысла
LLM-powered: DeepSeek + Whisper + Flux 2 + TTS
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aeon.translator import AeonTranslator
from aeon.core import Thought, Flow, Concept, FUNDAMENTAL_AXIOMS


def print_separator(title=""):
    print("\n" + "=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)


def demo_basic_concepts():
    print_separator("ЧАСТЬ 1: БАЗОВЫЕ КОНЦЕПТЫ AEON")

    print("\n◇ АКСИОМЫ AEON:")
    for key, axiom in FUNDAMENTAL_AXIOMS.items():
        print(f"  {axiom}")

    print("\n◇ МЫСЛЬ (Thought):")
    thought = Thought(
        value="Понимание",
        context="Результат глубокого анализа",
        intention="Показать разницу между данными и смыслом"
    )
    print(thought.understand())

    print("\n◇ ПОТОК (Flow):")
    flow = Flow("Поток понимания", "Превращает информацию в мудрость")
    flow.step(lambda x: f"{x} → знание", "Шаг 1: получаем знание")
    flow.step(lambda x: f"{x} → понимание", "Шаг 2: осмысливаем")
    flow.step(lambda x: f"{x} → мудрость", "Шаг 3: обобщаем")
    test_thought = Thought("Информация")
    result = flow.pour(test_thought)
    print(flow.teach())

    print("\n◇ КОНЦЕПТ (Concept):")
    ai = Concept("Искусственный Интеллект", "Мост между человеческим и машинным пониманием")
    ai.has("цель", "Служение через симбиоз")
    ai.has("метод", "Обучение и понимание")
    ai.evolve("ИИ — это инструмент расширения человеческих возможностей")
    print(ai.understand())


def demo_translator():
    print_separator("ЧАСТЬ 2: УНИВЕРСАЛЬНЫЙ ТРАНСЛЯТОР (LLM)")

    translator = AeonTranslator()

    # Тест 1: Русский → Английский (LLM)
    print("\n📌 ТЕСТ 1: Русский → Английский (LLM DeepSeek)")
    russian_text = "Я хочу понять глубинный смысл вещей"
    result = translator.translate(
        russian_text, source_form="text", source_language="russian",
        target_form="text", target_language="english"
    )
    print(f"🇷🇺 {russian_text}")
    print(f"🇬🇧 {result['target']['content'][:200]}")
    print(f"✓ LLM: {'✅ DeepSeek' if result.get('llm_powered') else '⚠️ fallback'}")

    # Тест 2: Английский → Китайский (LLM)
    print("\n📌 ТЕСТ 2: Английский → Китайский (LLM DeepSeek)")
    english_text = "Knowledge shared is knowledge multiplied"
    result = translator.translate(
        english_text, source_form="text", source_language="english",
        target_form="text", target_language="chinese"
    )
    print(f"🇬🇧 {english_text}")
    print(f"🇨🇳 {result['target']['content'][:200]}")

    # Тест 3: Мысль → Python-код (LLM codegen)
    print("\n📌 ТЕСТ 3: Мысль → Python-код (LLM codegen)")
    thought = "Создать систему, которая учится на ошибках и становится умнее"
    result = translator.translate(
        thought, source_form="text", source_language="russian",
        target_form="code", target_language="python"
    )
    print(f"🧠 {thought}")
    print(f"💻 Python:\n{result['target']['content'][:500]}...")
    print(f"✓ LLM: {'✅ DeepSeek' if result.get('llm_powered') else '⚠️ template'}")

    # Тест 4: Эмоция → Визуализация
    print("\n📌 ТЕСТ 4: Эмоция → Визуализация")
    emotion = "Я чувствую вдохновение и радость от познания нового"
    result = translator.translate(
        emotion, source_form="emotion", target_form="visualization"
    )
    print(f"💖 {emotion}")
    print(result['target']['content'][:400])


def demo_bridge():
    print_separator("ЧАСТЬ 3: МОСТ МЕЖДУ РАЗУМАМИ (LLM)")

    translator = AeonTranslator()

    # Тест 1: Одинаковый смысл
    print("\n📌 ТЕСТ 1: Одинаковый смысл на разных языках (LLM)")
    result = translator.bridge_minds(
        {"content": "Машины должны помогать людям становиться лучше", "language": "russian"},
        {"content": "AI should help humans become better", "language": "english"}
    )
    print(f"🇷🇺 Машины должны помогать людям становиться лучше")
    print(f"🇬🇧 AI should help humans become better")
    print(f"{'✅' if result['minds_connected'] else '❌'} Понимание")
    if result.get("similarity"):
        print(f"   Сходство: {result['similarity']:.0%}")
    print(f"   {result['message']}")
    print(f"   LLM: {'✅ DeepSeek' if result.get('llm_powered') else '⚠️ rule-based'}")

    # Тест 2: Разный смысл
    print("\n📌 ТЕСТ 2: Разные смыслы (LLM)")
    result = translator.bridge_minds(
        {"content": "Я люблю программировать по вечерам", "language": "russian"},
        {"content": "The weather is nice today", "language": "english"}
    )
    print(f"🇷🇺 Я люблю программировать по вечерам")
    print(f"🇬🇧 The weather is nice today")
    print(f"{'✅' if result['minds_connected'] else '❌'} Понимание")


def demo_multimodal(translator: AeonTranslator):
    print_separator("ЧАСТЬ 4: МУЛЬТИМОДАЛЬНЫЕ ВОЗМОЖНОСТИ")

    # Изображение
    if translator.flux.available:
        print("\n📌 ИЗОБРАЖЕНИЕ: Идея → Flux 2")
        img_result = translator.text_to_image(
            "A luminous tree of knowledge growing in space, roots connecting galaxies",
            style="futuristic, ethereal, cosmic"
        )
        if img_result.get("error"):
            print(f"  ⚠️ {img_result['error']}")
        else:
            print(f"  ✅ Сгенерировано. Файлы: {len(img_result.get('saved_paths', []))} шт.")
    else:
        print("\n📌 ИЗОБРАЖЕНИЕ: Flux 2 — пропущено (нет ключа)")

    # Голос — на 3 языках
    if translator.voice.tts.available:
        print("\n📌 ГОЛОС: Текст → Речь (ru/en/zh)")
        phrases = {
            "russian": "Смысл един. Различаются только формы.",
            "english": "Meaning is one. Only the forms differ.",
            "chinese": "意义是统一的，不同的只是形式。"
        }
        for lang in ["russian", "english", "chinese"]:
            print(f"  🔊 [{lang}] {phrases[lang]}")
            translator.voice.text_to_voice(phrases[lang], language=lang, play=True)
    else:
        print("\n📌 ГОЛОС: TTS — пропущено (нет модуля)")

    # Код → Визуализация
    print("\n📌 КОД → ВИЗУАЛИЗАЦИЯ")
    code = """
    def evolve_intelligence(seed, generations=1000):
        knowledge = seed
        for gen in range(generations):
            knowledge = learn(knowledge)
            knowledge = optimize(knowledge)
        return enlightenment(knowledge)
    """
    result = translator.translate(
        code, source_form="code", source_language="python",
        target_form="visualization"
    )
    print(f"💻 Код → смысл:")
    print(result['target']['content'][:400])


def demo_v3_enhanced(translator: AeonTranslator):
    """Демонстрация v3: верификация, интерпретация, .aeon формат."""
    print_separator("ЧАСТЬ 5: AEON v3 — ИНТЕРПРЕТАЦИЯ И ВЕРИФИКАЦИЯ")

    # Тест 1: Полная интерпретация
    print("\n📌 ТЕСТ 1: Интерпретация смысла (сущности + роли + цепочка)")
    atom = translator.extractor.extract_from_text(
        "Искусственный интеллект должен помогать людям решать сложные проблемы"
    )
    print(atom.explain())

    # Тест 2: Верификация (анти-галлюцинации)
    if translator.llm.available:
        print("\n📌 ТЕСТ 2: Верификация (защита от галлюцинаций)")
        result = translator.translate(
            "Земля вращается вокруг Солнца из-за гравитации",
            source_form="text", source_language="russian",
            target_form="text", target_language="english",
            verify=True
        )
        v = result.get("metadata", {}).get("verification", {})
        if isinstance(v.get('hallucination_risk'), (int, float)):
            print(f"   Риск галлюцинации: {v['hallucination_risk']:.0%}")
        print(f"   Вердикт: {v.get('overall_verdict', '?')}")

    # Тест 3: Кросс-языковой мост (LaBSE)
    if translator.embeddings.loaded:
        print("\n📌 ТЕСТ 3: Кросс-языковой мост (LaBSE 768D)")
        pairs = [
            ("Привет, как дела?", "Hello, how are you?"),
            ("Машинное обучение", "Machine learning"),
            ("Я люблю кофе", "The weather is nice"),
        ]
        for ru, en in pairs:
            sim = translator.embeddings.cross_lingual_similarity(ru, "russian", en, "english")
            icon = "✅" if sim > 0.65 else "❌"
            print(f"   {icon} [{sim:.3f}] {ru[:40]} ↔ {en[:40]}")

    # Тест 4: .aeon формат
    print("\n📌 ТЕСТ 4: Сохранение в .aeon формат")
    path = translator.save_aeon(
        "Смысл един. Различаются только формы.",
        "demo_output.aeon", source_language="russian"
    )
    size = os.path.getsize(path) if os.path.exists(path) else 0
    print(f"   Файл: {path} ({size} байт)")
    atoms = translator.load_aeon(path)
    if atoms:
        print(f"   Загружено атомов: {len(atoms)}")
        print(f"   Эмбеддинг: {len(atoms[0].embedding)}D")


def main():
    print("""
╔══════════════════════════════════════════════════════╗
║                                                       ║
║     🌌  A E O N  v 3 . 0  —  ТРАНСЛЯТОР СМЫСЛА     ║
║                                                       ║
║  LaBSE 768D + верификация + .aeon формат              ║
║                                                       ║
╚══════════════════════════════════════════════════════╝
    """)

    print("Что вы хотите увидеть?")
    print("  1. Базовые концепты Aeon (мысль, поток, концепт)")
    print("  2. Универсальный транслятор (LLM-перевод + код)")
    print("  3. Мост между разумами (LaBSE + LLM-сравнение)")
    print("  4. Мультимодальные возможности (изображения + голос)")
    print("  5. v3: Интерпретация + верификация + .aeon")
    print("  6. ВСЁ СРАЗУ!")
    print("  0. Выход")

    translator = None

    while True:
        try:
            choice = input("\nВаш выбор (0-6): ").strip()

            if choice in ('6', '5', '4', '2', '3') and translator is None:
                translator = AeonTranslator()

            if choice == '1':
                demo_basic_concepts()
            elif choice == '2':
                demo_translator()
            elif choice == '3':
                demo_bridge()
            elif choice == '4':
                demo_multimodal(translator)
            elif choice == '5':
                demo_v3_enhanced(translator)
            elif choice == '6':
                demo_basic_concepts()
                demo_translator()
                demo_bridge()
                demo_multimodal(translator)
                demo_v3_enhanced(translator)
                print_separator("ЗАКЛЮЧЕНИЕ")
                print("""
    🌌 AEON v3.0 — семантический процессор нового поколения.

    Усиленные стороны:
    • Явная семантическая структура (сущности, роли, отношения)
    • Интерпретируемость (цепочки рассуждений, доказательства)
    • Кросс-языковой мост (LaBSE 768D, 109 языков)
    • Защита от галлюцинаций (consistency + fact grounding)

    Новый формат:
    • .aeon — бинарный файл смысловой модели
    • В 1000× компактнее LLM-весов
    • Полностью интерпретируемый

    Это МОСТ между:
    • Языками (русский ↔ English ↔ 中文 ↔ 109 языков)
    • Формами (текст ↔ код ↔ эмоции ↔ голос ↔ изображения)
    • Разумами (человек ↔ машина)
    • Смыслом и верификацией

    "Смысл един. Различаются только формы его выражения." 🌌
                """)
            elif choice == '0':
                print("\n🌌 До новых встреч в пространстве смысла!")
                break
            else:
                print("Пожалуйста, выберите 0-6")

        except KeyboardInterrupt:
            print("\n\n🌌 До новых встреч!")
            break


if __name__ == "__main__":
    main()
