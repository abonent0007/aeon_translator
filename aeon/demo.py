#!/usr/bin/env python3
"""
Демонстрация LOGOS Semantic Analysis
LLM-powered: DeepSeek + Whisper + Flux 2 + TTS
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aeon.embeddings import EmbeddingEngine
from aeon.extractor import MeaningExtractor
from aeon.llm_client import DeepSeekClient
from aeon.metrics import METRICS, reset_metrics
from aeon.testing import MockLLM
from aeon.translator import AeonTranslator
from aeon.verification import VerificationEngine
from aeon.core import Thought, Flow, Concept, FUNDAMENTAL_AXIOMS


def print_separator(title=""):
    print("\n" + "=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)


def demo_basic_concepts():
    print_separator("ЧАСТЬ 1: БАЗОВЫЕ КОНЦЕПТЫ LOGOS")

    print("\n◇ АКСИОМЫ LOGOS:")
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
    print_separator("ЧАСТЬ 5: ИНТЕРПРЕТАЦИЯ И ВЕРИФИКАЦИЯ")

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


# ═══════════════════════════════════════════════════════════════
# Verification 2.0 demo (CLI: --text --verify --latency-ms --real)
# ═══════════════════════════════════════════════════════════════

DEMO_RESPONSES = {
    "Analyze the following text": {
        "intent": "statement",
        "domain": "philosophy",
        "entities": [
            {"name": "Сократ", "type": "person", "role": "agent",
             "span": "Сократ", "confidence": 0.9},
            {"name": "Афины", "type": "object", "role": "location",
             "span": "Афины", "confidence": 0.85},
        ],
        "semantic_roles": {"agent": "Сократ", "location": "Афины"},
        "evidence": ["Я знаю, что ничего не знаю."],
        "explanation_chain": [
            "Сократ признаёт собственное незнание",
            "Афины осудили Сократа на смерть в 399 году до н. э.",
        ],
        "confidence_breakdown": {"intent": 0.9, "domain": 0.85,
                                 "entities": 0.9, "roles": 0.8},
        "complexity": 0.4,
        "urgency": 0.1,
        "extraction_confidence": 0.88,
        "semantic_tokens": ["мудрость", "незнание", "суд"],
    },
    "Reconstruction candidate 'ἴδρως": {"claims": [
        {"claim": "cand-1", "quote": "…τὸ δὲ λέπτον", "contradicts": False,
         "confidence": 0.9, "reasoning": "surviving context brackets the gap"},
    ]},
    "Reconstruction candidate 'τρόμος": {"claims": [
        {"claim": "cand-2", "quote": "χρῶι πῦρ ὐπαδεδρόμηκεν…", "contradicts": False,
         "confidence": 0.86, "reasoning": "continuation plausible in context"},
    ]},
    "Detective": {"claims": [
        {"claim": "Сократ признаёт собственное незнание",
         "quote": "οὐκ οἶδα", "contradicts": False,
         "confidence": 0.92, "reasoning": "точная цитата в источнике"},
        {"claim": "Обвинители упомянуты как источник опыта",
         "quote": "ὑπὸ τῶν ἐμῶν κατηγόρων", "contradicts": False,
         "confidence": 0.9, "reasoning": "точная цитата"},
    ]},
    "Expert": {"claims": [
        {"claim": "Сократ признаёт собственное незнание",
         "status": "unknown", "source": "", "confidence": 0.4,
         "reasoning": "внешние источники не подключены в demo"},
    ]},
    "Logician": {"contradictions": [], "coherence": 0.9,
                 "reasoning": "внутренних противоречий нет"},
    "You reconstruct": {"hypotheses": [
        {"text": "ἴδρως κακχέεται", "confidence": 0.78,
         "evidence": "Sapph. 31, ст. 13 (Voigt): восстановление по контексту строфы"},
        {"text": "τρόμος δὲ παῖσαν ἄγρει", "confidence": 0.55,
         "evidence": "продолжение строфы; менее надёжно"},
    ], "status": "ok"},
    "select ONE reading": {
        "chosen_index": 0, "confidence": 0.71,
        "reasoning": "грамматика и контекст согласуются с первым кандидатом; "
                     "illustrative, not calibrated",
    },
    "LEXICAL": {"findings": [
        {"kind": "lemma", "value": "μῆνις", "span": [15, 21],
         "confidence": 0.85, "note": "acc. sg."},
    ], "confidence": 0.82, "handoff": {"lemmas": ["μῆνις"], "morphology": ["acc.sg"]}},
    "SYNTACTIC": {"findings": [
        {"kind": "role", "value": "object", "span": [15, 21],
         "confidence": 0.8, "note": "accusative object of ἄειδε"},
    ], "confidence": 0.8, "handoff": {"clauses": ["imperative clause"], "deviations": []}},
    "SEMANTIC": {"findings": [
        {"kind": "proposition", "value": "поющий призывает воспеть гнев Ахилла",
         "span": None, "confidence": 0.82, "note": ""},
    ], "confidence": 0.82, "handoff": {"propositions": ["invocation of the wrath"], "ambiguities": []}},
    "PRAGMATIC": {"findings": [
        {"kind": "speech_act", "value": "invocation (prayer to Muse)",
         "span": None, "confidence": 0.8, "note": "эпическая формула"},
    ], "confidence": 0.8, "handoff": {"speech_acts": ["invocation"], "implicatures": []}},
    "HISTORIAN": {"insights": [
        {"claim": "Илиада сложилась в рамках устной эпической традиции VIII в. до н.э.",
         "angle": "historical_context", "confidence": 0.7, "source_refs": ["Q6691"]},
    ], "confidence": 0.7, "evidence": ["эпические формулы"]},
    "PHILOSOPHER": {"insights": [
        {"claim": "Гнев (μῆνις) Ахилла — тема этической ответственности",
         "angle": "philosophical", "confidence": 0.65, "source_refs": []},
    ], "confidence": 0.65, "evidence": ["концепт μῆνις"]},
    "LINGUIST": {"insights": [
        {"claim": "Формула «μῆνιν ἄειδε» — маркер устной традиции",
         "angle": "language_history", "confidence": 0.75, "source_refs": []},
    ], "confidence": 0.75, "evidence": ["формульность"]},
    "ESOTERIC": {"insights": [], "confidence": 0.3,
                 "evidence": ["нет исторически засвидетельствованной символики"]},
}


def _offline_embeddings():
    engine = EmbeddingEngine()
    engine.available = False  # без загрузки моделей
    return engine


def run_verify_demo(text_path: str, verify_mode: str, latency_ms: float,
                    use_real: bool, language: str | None = None,
                    reconstruct: bool = False, layers: str | None = None,
                    focus: str | None = None,
                    variant_readings: str | None = None,
                    variant_work: str | None = None,
                    offline_pleiades: str | None = None,
                    save_aeon: str | None = None) -> None:
    """Demo: атом + trace верификации + метрики (мок с задержкой или реальный LLM)."""
    from pathlib import Path

    path = Path(text_path)
    if not path.exists():
        print(f"❌ Файл не найден: {text_path}")
        return
    text = path.read_text(encoding="utf-8").strip()

    language_pack = None
    if language:
        from aeon.language import get as get_pack

        language_pack = get_pack(language)
        text = language_pack.normalize(text)
        markers = language_pack.detect_markers(text)
        print(f"Языковой пак: {language_pack.display_name} ({language_pack.iso_code}, "
              f"{language_pack.period[0]}..{language_pack.period[1]})")
        print(f"  маркеров: {len(markers)} | is_fragment: {language_pack.is_fragment(text)}")
        for marker in markers[:5]:
            print(f"    • {marker.kind}: {marker.text!r} @ {marker.start}")

    print_separator(f"LOGOS DEMO — verify={verify_mode} — {path.name}")
    print(f"Текст ({len(text)} симв.): {text[:110]}...")

    llm = None
    if use_real:
        llm = DeepSeekClient()
        if not llm.available:
            print("⚠️ DEEPSEEK_API_KEY не задан — fallback на MockLLM")
            llm = None
    if llm is None:
        llm = MockLLM(responses=DEMO_RESPONSES, latency_ms=latency_ms)
        print(f"LLM: MockLLM (латентность {latency_ms:g} ms/вызов — имитация сети; "
              f"canned-ответы, illustrative, not calibrated)")

    extractor = MeaningExtractor(llm_client=llm, embedding_engine=_offline_embeddings())
    verification = VerificationEngine(llm_client=llm)
    verification.embeddings = _offline_embeddings()

    reset_metrics()
    with METRICS.timeit("atom"):
        with METRICS.timeit("atom_network"):
            atom = extractor.extract_from_text(text, "auto")
            if language_pack is not None:
                atom.anchor_language = language_pack.iso_code
            result = None
            reconstruction = None
            chain_result = None
            focus_run = None
            variant_run = None
            if verify_mode != "off":
                from aeon.verification import build_claims  # contract v1

                claims = build_claims(atom, trace_id=atom.meaning_hash)
                result = verification.verify_atom(
                    text, claims, [e.name for e in atom.entities],
                    trace_id=atom.meaning_hash, mode=verify_mode,
                )
            reconstruction = None
            if reconstruct and atom.is_fragment:
                from aeon.fragments import FragmentHypothesisEngine

                engine = FragmentHypothesisEngine(llm_client=llm, verifier=verification)
                reconstruction = engine.reconstruct(atom, pack=language_pack)

        print(f"\nАТОМ: {atom}")
        print(f"  сущностей: {len(atom.entities)} | evidence: {len(atom.evidence)}"
              f" | completeness: {atom.completeness_score:.2f}"
              f" | is_fragment: {atom.is_fragment}")

        if result is None:
            print("\n(верификация выключена: --verify=off)")
        else:
            print(f"\n🔍 TRACE ВЕРИФИКАЦИИ (trace_id={atom.meaning_hash[:8]}):")
            for step in result["reasoning_trace"]:
                print(f"  • {step['agent']:<9} {step['verdict']:<32} "
                      f"conf={step['confidence']:.2f}  {step['reasoning'][:56]}")
            combined = result["combined"]
            print(f"\nCVI: {result['cvi']:.2f} | вердикт: {combined['verdict']}"
                  f" | abstained: {result['abstained']}"
                  f" | needs_review: {combined['needs_review']}")
            print(f"Legacy-проекция: verdict={result['overall_verdict']}"
                  f" risk={result['hallucination_risk']:.0%}")
            if result["abstained"]:
                print("⚠️ Система воздержалась («Я не знаю») — недостаточно данных")

        if reconstruct:
            if reconstruction is None:
                print("\n🧩 РЕКОНСТРУКЦИЯ: не запускалась (текст не фрагментарен)")
            else:
                print(f"\n🧩 РЕКОНСТРУКЦИЯ (status={reconstruction.status}):")
                if reconstruction.status == "ok":
                    for hypothesis in reconstruction.hypotheses:
                        print(f"  [{hypothesis.confidence:.2f}] {hypothesis.text}")
                        print(f"       evidence: {hypothesis.evidence[:70]}")
                else:
                    print(f"  ⚠️ no_reconstruction_possible: "
                          f"{reconstruction.no_reconstruction.reason}")
                print(f"  density: {reconstruction.fragment_density:.5f}"
                      f" | маркеров: {reconstruction.markers_count}")

        if layers:
            from aeon.config import ConfigError
            from aeon.linguistics import ChainOfLinguistics

            layer_list = (None if layers == "all"
                          else [part.strip() for part in layers.split(",") if part.strip()])
            chain = ChainOfLinguistics(llm_client=llm)
            with METRICS.timeit("atom_network"):
                try:
                    chain_result = chain.run(text, original_text=text,
                                             layers=layer_list, pack=language_pack,
                                             trace_id=atom.meaning_hash)
                except ConfigError as exc:
                    print(f"\n🔬 LINGUISTIC LAYERS: {exc}")
                    chain_result = None
            if chain_result is not None:
                print(f"\n🔬 LINGUISTIC LAYERS (status={chain_result.status}, "
                      f"llm_calls={chain_result.llm_calls}):")
                for layer_result in chain_result.layers:
                    print(f"  • {layer_result.layer:<9} conf={layer_result.confidence:.2f} "
                          f"findings={len(layer_result.findings)}")
                    for finding in layer_result.findings[:2]:
                        print(f"      {finding.kind}={finding.value!r} "
                              f"conf={finding.confidence:.2f}")

        if focus:
            from aeon.config import ConfigError
            from aeon.focus import MultiFocusOrchestrator

            role_list = (None if focus == "all"
                         else [part.strip() for part in focus.split(",") if part.strip()])
            orchestrator = MultiFocusOrchestrator(llm_client=llm)
            with METRICS.timeit("atom_network"):
                try:
                    focus_run = orchestrator.run(atom, roles=role_list, pack=language_pack,
                                                 trace_id=atom.meaning_hash)
                except ConfigError as exc:
                    print(f"\n🎭 MULTI-FOCUS: {exc}")
                    focus_run = None
            if focus_run is not None:
                print(f"\n🎭 MULTI-FOCUS (status={focus_run.status}, "
                      f"llm_calls={focus_run.llm_calls}):")
                for analysis in focus_run.roles:
                    print(f"  • {analysis.role:<11} conf={analysis.confidence:.2f} "
                          f"insights={len(analysis.insights)}")
                    for insight in analysis.insights[:2]:
                        print(f"      [{insight.angle}] {insight.claim[:70]}")
                if focus_run.all_disagree:
                    print("  ⚠️ all_disagree=True (роли расходятся в формулировках)")

        if variant_readings:
            from aeon.config import ConfigError
            from aeon.variants import VariantEngine, load_apparatus

            work_hint = variant_work or path.stem
            with METRICS.timeit("atom_network"):
                try:
                    apparatus = load_apparatus(variant_readings)
                    variant_engine = VariantEngine(llm_client=llm,
                                                   verifier=verification)
                    variant_run = variant_engine.run(atom, apparatus,
                                                     work_hint=work_hint,
                                                     trace_id=atom.meaning_hash)
                except (ConfigError, ValueError) as exc:
                    print(f"\n📜 VARIANT READINGS: {exc}")
                    variant_run = None
            if variant_run is not None:
                print(f"\n📜 VARIANT READINGS (work={variant_run.work}, "
                      f"llm_calls={variant_run.llm_calls}):")
                for selection in variant_run.selections:
                    chosen_text = (selection.chosen.text[:60]
                                   if selection.chosen else "—")
                    print(f"  • line {selection.locus.line:<4} "
                          f"{selection.status:<22} conf={selection.confidence:.2f} "
                          f"{chosen_text}")
                    for vetoed_text, editions in selection.editions_vetoed.items():
                        print(f"      veto: {vetoed_text[:40]!r} "
                              f"({', '.join(editions)})")

        if offline_pleiades:
            from aeon.offline import OfflineDumpError, get_adapter

            adapter = get_adapter("pleiades")
            try:
                load_result = adapter.load(offline_pleiades)
                print(f"\n🗄️ OFFLINE PLEIADES: status={load_result['status']} "
                      f"v{load_result['dump_version']} rows={load_result['rows']}")
                provenance = adapter.provenance()
                if provenance is not None:
                    print(f"  license: {provenance.license} | "
                          f"sha256: {provenance.license_file_sha256[:16]}… | "
                          f"bundle: {provenance.bundle_size_bytes} B")
                age = adapter.dump_age_days()
                if age is not None:
                    print(f"  dump age: {age} days")
                sample = adapter.lookup("579885")
                if sample is not None:
                    print(f"  sample lookup: {sample.id} → {sample.title} "
                          f"({sample.source}, v{sample.dump_version})")
            except OfflineDumpError as exc:
                print(f"\n🗄️ OFFLINE PLEIADES: {exc}")

        if save_aeon:
            from aeon.format import build_thresholds_snapshot, dump_v2, write_v2

            if not atom.thresholds_snapshot:
                atom.thresholds_snapshot = build_thresholds_snapshot()
            requested = ["extract"]
            executed = ["extract"]
            halted = []
            if verify_mode != "off":
                requested.append("verification")
                if result is not None:
                    executed.append("verification")
            if reconstruct:
                requested.append("reconstruction")
                if reconstruction is not None:
                    executed.append("reconstruction")
            if layers:
                requested.append("linguistics")
                if chain_result is not None:
                    executed.append("linguistics")
                    if chain_result.status.startswith("halted_at_"):
                        halted.append({"step": "linguistics",
                                       "reason": chain_result.status})
            if focus:
                requested.append("focus")
                if focus_run is not None:
                    executed.append("focus")
            if variant_readings:
                requested.append("variant_readings")
                if variant_run is not None:
                    executed.append("variant_readings")
            doc = dump_v2(
                atom,
                source={"content": text, "form": "text", "language": "auto"},
                traces={
                    "verification": result,
                    "linguistics": (chain_result.to_dict() if chain_result else None),
                    "reconstruction": (reconstruction.to_dict() if reconstruct
                                       and reconstruction else None),
                    "focus": (focus_run.to_dict() if focus and focus_run else None),
                    "variant_readings": (variant_run.to_dict()
                                         if variant_run else None),
                },
                metadata={
                    "language_pack": (language_pack.iso_code
                                      if language_pack else None),
                    "llm_provider": "mock" if not use_real else "deepseek",
                    "llm_model": (getattr(llm, "model", None) if use_real else None),
                },
                pipeline={"steps_requested": requested, "steps_executed": executed,
                          "steps_halted": halted, "steps_failed": []},
                mock=not use_real,
                trace_id=atom.meaning_hash,
            )
            write_v2(save_aeon, doc)
            print(f"\n💾 .aeon v2 сохранён: {save_aeon}")

    METRICS.record_atom()
    print_separator("METRICS")
    print(METRICS.format_summary())
    mock_calls = getattr(llm, "calls", None)
    if mock_calls is not None:
        print(f"  LLM-вызовов (mock): {len(mock_calls)} × {latency_ms:g} ms = "
              f"{len(mock_calls) * latency_ms / 1000.0:.2f} s (экстраполяция сети)")
    else:
        print(f"  LLM: real ({getattr(llm, 'model', '?')}) — реальная сеть, "
              f"время в avg_time_per_atom")


def main():
    parser = argparse.ArgumentParser(
        description="LOGOS demo: интерактив или Verification 2.0 (--text)"
    )
    parser.add_argument("--text", type=str, default=None, help="файл с текстом для анализа")
    parser.add_argument("--verify", choices=["off", "basic", "full"], default="off",
                        help="режим верификации Verification 2.0")
    parser.add_argument("--latency-ms", type=float, default=200.0,
                        help="мок-задержка LLM на вызов (для замеров)")
    parser.add_argument("--real", action="store_true",
                        help="использовать реальный LLM (нужен DEEPSEEK_API_KEY в .env)")
    parser.add_argument("--language", type=str, default=None,
                        help="ISO-код языкового пака для нормализации/маркеров (например, grc)")
    parser.add_argument("--reconstruct", action="store_true",
                        help="Fragment Hypothesis Engine (шаг 2.3): гипотезы восстановления")
    parser.add_argument("--layers", type=str, default=None,
                        help="Chain-of-Linguistics (шаг 2.4): 'all' или 'lexical,syntactic,...'")
    parser.add_argument("--focus", type=str, default=None,
                        help="Multi-focus (шаг 2.5): 'all' (без esoteric) или 'historian,philosopher,...'")
    parser.add_argument("--variant-readings", type=str, default=None,
                        help="Apparatus criticus JSON (шаг 3.5): выбор среди attested readings")
    parser.add_argument("--variant-work", type=str, default=None,
                        help="Ожидаемая работа (work-guard); default: имя текстового файла")
    parser.add_argument("--offline-pleiades", type=str, default=None,
                        help="Путь к JSONL-дампу Pleiades (offline adapter, шаг 2.6)")
    parser.add_argument("--save-aeon", type=str, default=None,
                        help="Сохранить результат как .aeon v2 (шаг 3.1)")
    parser.add_argument("--load-aeon", type=str, default=None,
                        help="Прочитать .aeon v2 (или мигрировать v1) и показать сводку")
    args = parser.parse_args()

    if args.load_aeon:
        from aeon.format import AeonSchemaError, load_v1_and_migrate, load_v2

        try:
            doc = load_v2(args.load_aeon)
        except AeonSchemaError:
            doc = load_v1_and_migrate(args.load_aeon)
        pipeline = doc["metadata"]["pipeline"]
        loaded_traces = [key for key, value in doc["traces"].items() if value is not None]
        print(f"\n📂 .aeon v{doc['aeon_version']} | mock={doc['metadata']['mock']} | "
              f"steps={pipeline['steps_executed']}")
        print(f"   atom: {doc['atom']['intent']}/{doc['atom']['domain']} | "
              f"traces: {loaded_traces}")
        return

    if args.text:
        run_verify_demo(args.text, args.verify, args.latency_ms, args.real,
                        language=args.language, reconstruct=args.reconstruct,
                        layers=args.layers, focus=args.focus,
                        variant_readings=args.variant_readings,
                        variant_work=args.variant_work,
                        offline_pleiades=args.offline_pleiades,
                        save_aeon=args.save_aeon)
        return

    print("""
╔══════════════════════════════════════════════════════╗
║                                                       ║
║     🌌  L O G O S  —  SEMANTIC ANALYSIS     ║
║                                                       ║
║  LaBSE 768D + верификация + .aeon формат              ║
║                                                       ║
╚══════════════════════════════════════════════════════╝
    """)

    print("Что вы хотите увидеть?")
    print("  1. Базовые концепты LOGOS (мысль, поток, концепт)")
    print("  2. Универсальный транслятор (LLM-перевод + код)")
    print("  3. Мост между разумами (LaBSE + LLM-сравнение)")
    print("  4. Мультимодальные возможности (изображения + голос)")
    print("  5. Интерпретация + верификация + .aeon")
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
    🌌 LOGOS Semantic Analysis — семантический процессор нового поколения.

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
