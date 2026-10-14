"""
Консольный интерфейс Aeon v2.0
"""

import sys
import os
from .translator import AeonTranslator

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    C = {
        'title': Fore.CYAN + Style.BRIGHT,
        'success': Fore.GREEN,
        'info': Fore.YELLOW,
        'error': Fore.RED,
        'reset': Style.RESET_ALL,
        'bold': Style.BRIGHT,
        'dim': Fore.WHITE + Style.DIM,
        'magenta': Fore.MAGENTA + Style.BRIGHT
    }
except ImportError:
    class FakeColor:
        def __getattr__(self, name):
            return ''
    C = FakeColor()
    Fore = FakeColor()
    Style = FakeColor()


def print_banner():
    banner = f"""
{C['title']}╔══════════════════════════════════════════════════════╗
║                                                       ║
║     🌌  A E O N  v 3 . 0  —  ТРАНСЛЯТОР СМЫСЛА      ║
║                                                       ║
║  LaBSE 768D + верификация + .aeon формат              ║
║                                                       ║
║  "Смысл един. Различаются только формы."              ║
║                                                       ║
╚══════════════════════════════════════════════════════╝{C['reset']}
"""
    print(banner)


def print_help():
    help_text = f"""
{C['bold']}ДОСТУПНЫЕ КОМАНДЫ:{C['reset']}

{C['info']}translate{C['reset']} (t)    — перевести смысл
    {C['dim']}t текст [from=язык] [to=язык] [form=форма]{C['reset']}
    {C['dim']}Пример: t "Я хочу понять мир" to=english{C['reset']}

{C['info']}code{C['reset']} (c)        — текст → код
    {C['dim']}c описание [lang=python|javascript]{C['reset']}
    {C['dim']}Пример: c "Сортировка массива пузырьком"{C['reset']}

{C['info']}bridge{C['reset']} (b)      — соединить два разума
    {C['dim']}b мысль1 | мысль2{C['reset']}

{C['info']}voice{C['reset']} (v)       — голосовые команды (Whisper + TTS)
    {C['dim']}v record [sec=10] [ru/en/zh]     — запись с микрофона → текст{C['reset']}
    {C['dim']}v speak ru ТЕКСТ                  — озвучить на русском{C['reset']}
    {C['dim']}v speak en ТЕКСТ                  — озвучить на английском{C['reset']}
    {C['dim']}v speak zh ТЕКСТ                  — озвучить на китайском{C['reset']}
    {C['dim']}v demo                            — демо озвучки на 3 языках{C['reset']}
    {C['dim']}v translate файл.wav [to=lang]    — голосовой перевод{C['reset']}

{C['info']}image{C['reset']} (img)     — генерация изображений (Flux 2)
    {C['dim']}img текст [style=realistic]    — текст → картинка{C['reset']}
    {C['dim']}img emotion текст              — эмоция → картинка{C['reset']}

{C['info']}visualize{C['reset']} (viz) — визуализация смысла
    {C['dim']}viz текст{C['reset']}

{C['info']}verify{C['reset']} (vf)     — верифицировать смысл (анти-галлюцинации)
    {C['dim']}vf текст                         — проверить на галлюцинации{C['reset']}

{C['info']}save{C['reset']}           — сохранить смысл в .aeon файл
    {C['dim']}save текст [path=file.aeon]       — бинарный формат{C['reset']}

{C['info']}compare{C['reset']}        — сравнить два .aeon файла
    {C['dim']}compare file1.aeon file2.aeon{C['reset']}

{C['info']}search{C['reset']}         — семантический поиск
    {C['dim']}search запрос | кандидат1 | кандидат2 | ...{C['reset']}

{C['info']}explain{C['reset']} (x)   — полная интерпретация смысла
    {C['dim']}x текст                          — цепочка рассуждений + сущности{C['reset']}
{C['info']}stats{C['reset']}           — статус модулей и статистика
{C['info']}axioms{C['reset']}          — аксиомы Aeon
{C['info']}help{C['reset']} (h)        — эта справка
{C['info']}exit{C['reset']} (q)        — выход

{C['bold']}ЯЗЫКИ:{C['reset']} russian, english, chinese, japanese, german, french, spanish
{C['bold']}ФОРМЫ:{C['reset']}  text, code, visualization, image, voice, emotion
"""
    print(help_text)


def show_axioms():
    from .core import FUNDAMENTAL_AXIOMS
    print(f"\n{C['title']}◇ АКСИОМЫ AEON{C['reset']}\n")
    for key, axiom in FUNDAMENTAL_AXIOMS.items():
        print(f"{C['bold']}{axiom}{C['reset']}")


def show_stats(translator: AeonTranslator):
    s = translator.stats()
    print(f"\n{C['bold']}СТАТИСТИКА ТРАНСЛЯТОРА:{C['reset']}")
    print(f"  Переводов: {s['translations_performed']}")
    print(f"  Атомов в памяти: {s['unique_atoms_stored']}")
    print(f"\n{C['bold']}МОДУЛИ:{C['reset']}")
    for name, available in s['modules'].items():
        icon = "✅" if available else "⚠️"
        print(f"  {icon} {name}")


def parse_translate_args(args: str) -> dict:
    params = {'text': ''}
    text_parts = []
    for part in args.split():
        if '=' in part:
            key, value = part.split('=', 1)
            params[key] = value
        else:
            text_parts.append(part)
    params['text'] = ' '.join(text_parts)
    param_map = {
        'from': 'source_lang', 'to': 'target_lang',
        'form': 'target_form', 'source': 'source_form'
    }
    mapped = {}
    for key, value in params.items():
        mapped_key = param_map.get(key, key)
        mapped[mapped_key] = value
    return mapped


def run_cli():
    print_banner()
    translator = AeonTranslator()
    print(f"\n{C['info']}Введите 'help' для списка команд, 'exit' для выхода{C['reset']}\n")

    while True:
        try:
            command = input(f"{C['bold']}aeon>{C['reset']} ").strip()
            if not command:
                continue

            parts = command.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            # === EXIT ===
            if cmd in ['exit', 'quit', 'q']:
                print(f"\n{C['success']}🌌 Aeon завершает работу. Смысл сохранён.{C['reset']}")
                print(f"{C['dim']}Переводов выполнено: {translator.translation_count}{C['reset']}")
                break

            # === HELP ===
            elif cmd in ['help', 'h', '?']:
                print_help()

            # === AXIOMS ===
            elif cmd == 'axioms':
                show_axioms()

            # === STATS ===
            elif cmd == 'stats':
                show_stats(translator)

            # === DEMO ===
            elif cmd == 'demo':
                run_demo(translator)

            # === TRANSLATE ===
            elif cmd in ['translate', 't']:
                if not args:
                    print(f"{C['error']}Укажите текст для перевода{C['reset']}")
                    continue
                params = parse_translate_args(args)
                result = translator.translate(
                    content=params['text'],
                    source_form=params.get('source_form', 'text'),
                    source_language=params.get('source_lang', 'auto'),
                    target_form=params.get('target_form', 'text'),
                    target_language=params.get('target_lang', 'english')
                )
                print(f"\n{C['success']}✓ РЕЗУЛЬТАТ:{C['reset']}")
                print(f"{C['bold']}{result['target']['content'][:500]}{C['reset']}")
                print(f"\n{C['dim']}Смысл сохранён: {result['meaning_preserved']:.0%} | LLM: {'✅' if result.get('llm_powered') else '⚠️ rule-based'}{C['reset']}")

            # === CODE ===
            elif cmd in ['code', 'c']:
                if not args:
                    print(f"{C['error']}Опишите, какой код нужен{C['reset']}")
                    continue
                params = parse_translate_args(args)
                lang = params.get('target_lang', params.get('lang', 'python'))
                result = translator.translate(
                    content=params['text'],
                    source_form="text", source_language="auto",
                    target_form="code", target_language=lang
                )
                print(f"\n{C['success']}✓ СГЕНЕРИРОВАННЫЙ КОД ({lang}):{C['reset']}\n")
                print(result['target']['content'])
                print(f"\n{C['dim']}LLM: {'✅ DeepSeek' if result.get('llm_powered') else '⚠️ template'}{C['reset']}")

            # === BRIDGE ===
            elif cmd in ['bridge', 'b']:
                if '|' not in args:
                    print(f"{C['error']}Используйте | для разделения мыслей{C['reset']}")
                    continue
                parts_bridge = args.split('|')
                if len(parts_bridge) != 2:
                    print(f"{C['error']}Нужно ровно 2 мысли, разделённые |{C['reset']}")
                    continue
                mind_a = {"content": parts_bridge[0].strip(), "language": "auto"}
                mind_b = {"content": parts_bridge[1].strip(), "language": "auto"}
                result = translator.bridge_minds(mind_a, mind_b)
                print(f"\n{C['bold']}МОСТ МЕЖДУ РАЗУМАМИ:{C['reset']}")
                print(f"  Понимание: {'✅' if result['minds_connected'] else '❌'}")
                print(f"  Сходство: {result.get('similarity', 1 - result['semantic_distance']):.0%}")
                print(f"  Уровень: {result.get('understanding_level', '?')}")
                print(f"  {result['message']}")
                if result.get('explanation'):
                    print(f"  {C['dim']}{result['explanation']}{C['reset']}")
                if result.get('llm_powered'):
                    shared = result.get('shared_concepts', [])
                    if shared:
                        print(f"  Общие концепты: {', '.join(shared[:5])}")

            # === VOICE ===
            elif cmd in ['voice', 'v']:
                handle_voice(translator, args)

            # === IMAGE ===
            elif cmd in ['image', 'img']:
                handle_image(translator, args)

            # === VERIFY ===
            elif cmd in ['verify', 'vf']:
                if not args:
                    print(f"{C['error']}Укажите текст для верификации{C['reset']}")
                    continue
                result = translator.translate(args, source_form="text", source_language="auto",
                                              target_form="text", target_language="english", verify=True)
                v = result.get("metadata", {}).get("verification", {})
                print(f"\n{C['bold']}🔍 ВЕРИФИКАЦИЯ СМЫСЛА:{C['reset']}")
                print(f"  Консистентность: {v.get('consistency', {}).get('score', '?'):.0%}" if isinstance(v.get('consistency', {}).get('score'), (int, float)) else f"  Консистентность: ?")
                if isinstance(v.get('hallucination_risk'), (int, float)):
                    risk = v['hallucination_risk']
                    color = C['success'] if risk < 0.15 else C['info'] if risk < 0.35 else C['error']
                    print(f"  Риск галлюцинации: {color}{risk:.0%}{C['reset']}")
                print(f"  Вердикт: {v.get('overall_verdict', '?')}")

            # === SAVE (aeon format) ===
            elif cmd == 'save':
                if not args:
                    print(f"{C['error']}Укажите текст для сохранения{C['reset']}")
                    continue
                path = "output.aeon"
                text = args
                for p in args.split():
                    if p.startswith("path="):
                        path = p.split("=", 1)[1]
                        text = args.replace(p, "").strip()
                filepath = translator.save_aeon(text, path)
                atoms = translator.load_aeon(filepath)
                if atoms:
                    print(atoms[0].explain())

            # === COMPARE ===
            elif cmd == 'compare':
                files = args.split()
                if len(files) < 2:
                    print(f"{C['error']}Укажите два .aeon файла{C['reset']}")
                    continue
                result = translator.compare_aeon(files[0], files[1])
                print(f"\n{C['bold']}СРАВНЕНИЕ .AEON ФАЙЛОВ:{C['reset']}")
                print(f"  Смысловое расстояние: {result['semantic_distance']}")
                print(f"  Совпадение intent: {result['intent_match']}")
                print(f"  Совпадение domain: {result['domain_match']}")
                print(f"  Общие сущности: {result['common_entities']}")
                print(f"  Вердикт: {result['verdict']}")

            # === SEARCH ===
            elif cmd == 'search':
                if '|' not in args:
                    print(f"{C['error']}Формат: search запрос | кандидат1 | кандидат2 | ...{C['reset']}")
                    continue
                parts_search = [s.strip() for s in args.split('|')]
                if len(parts_search) < 2:
                    print(f"{C['error']}Нужен запрос и минимум 1 кандидат{C['reset']}")
                    continue
                query = parts_search[0]
                candidates = parts_search[1:]
                results = translator.semantic_search(query, candidates, top_k=min(5, len(candidates)))
                print(f"\n{C['bold']}🔍 СЕМАНТИЧЕСКИЙ ПОИСК:{C['reset']}")
                print(f"  Запрос: {query}")
                for i, r in enumerate(results, 1):
                    print(f"  {i}. [{r['score']:.4f}] {r['text'][:80]}")

            # === EXPLAIN ===
            elif cmd in ['explain', 'x']:
                if not args:
                    print(f"{C['error']}Укажите текст для интерпретации{C['reset']}")
                    continue
                atom = translator.extractor.extract_from_text(args)
                print(f"\n{C['title']}ИНТЕРПРЕТАЦИЯ СМЫСЛА:{C['reset']}")
                print(atom.explain())

            # === VISUALIZE ===
            elif cmd in ['visualize', 'viz']:
                if not args:
                    print(f"{C['error']}Укажите текст для визуализации{C['reset']}")
                    continue
                result = translator.translate(
                    content=args, source_form="text", source_language="auto",
                    target_form="visualization"
                )
                print(f"\n{C['success']}✓ ВИЗУАЛИЗАЦИЯ СМЫСЛА:{C['reset']}")
                print(result['target']['content'])

            else:
                # По умолчанию — перевод на английский
                result = translator.translate(
                    content=command, source_form="text", source_language="auto",
                    target_form="text", target_language="english"
                )
                print(f"\n{C['success']}→ {result['target']['content']}{C['reset']}")

        except KeyboardInterrupt:
            print(f"\n{C['info']}Нажмите 'exit' для выхода{C['reset']}")
        except Exception as e:
            print(f"{C['error']}Ошибка: {e}{C['reset']}")


def handle_voice(translator: AeonTranslator, args: str):
    """Обрабатывает голосовые команды: запись, озвучка (ru/en/zh), перевод."""
    sub_parts = args.split(maxsplit=1)
    sub_cmd = sub_parts[0].lower() if sub_parts else ""
    sub_args = sub_parts[1] if len(sub_parts) > 1 else ""

    lang_aliases = {
        "ru": "russian", "rus": "russian", "russian": "russian", "рус": "russian",
        "en": "english", "eng": "english", "english": "english", "анг": "english",
        "zh": "chinese", "cn": "chinese", "chi": "chinese", "chinese": "chinese", "кит": "chinese"
    }

    # ── voice record ──
    if sub_cmd == "record":
        sec = 10
        lang_hint = None
        for p in sub_args.split():
            if p.startswith("sec="):
                sec = int(p.split("=")[1])
            elif p in lang_aliases:
                lang_hint = lang_aliases[p]
        audio_path = translator.voice.stt.record_audio(duration=sec)
        if audio_path:
            result = translator.voice.voice_to_text(audio_path, language=lang_hint)
            lang_emoji = {"russian": "🇷🇺", "english": "🇬🇧", "chinese": "🇨🇳"}
            emoji = lang_emoji.get(result.get("language", ""), "🎤")
            print(f"\n{C['success']}{emoji} РАСПОЗНАНО [{result.get('language', '?')}]:{C['reset']}")
            print(f"  {result['text']}")
            os.unlink(audio_path)

    # ── voice speak ru/en/zh ТЕКСТ ──
    elif sub_cmd == "speak":
        spoke = False
        for alias, lang in lang_aliases.items():
            marker = f"{alias} "
            if sub_args.lower().startswith(marker):
                text = sub_args[len(marker):].strip()
                translator.voice.text_to_voice(text, language=lang, play=True)
                spoke = True
                break
        if not spoke:
            # По умолчанию — автоопределение языка текста → озвучка
            lang = "english"
            text = sub_args
            # Угадываем язык
            if any('\u4e00' <= c <= '\u9fff' for c in text):
                lang = "chinese"
            elif any(c in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя' for c in text.lower()):
                lang = "russian"
            translator.voice.text_to_voice(text, language=lang, play=True)

    # ── voice demo ──
    elif sub_cmd == "demo":
        if not translator.voice.tts.available:
            print(f"{C['error']}TTS недоступен. Установите: pip install edge-tts{C['reset']}")
            return
        print(f"\n{C['title']}🔊 ДЕМО: ОЗВУЧКА НА 3 ЯЗЫКАХ{C['reset']}\n")
        phrases = {
            "russian": "Смысл един. Различаются только формы.",
            "english": "Meaning is one. Only the forms differ.",
            "chinese": "意义是统一的，不同的只是形式。"
        }
        for lang in ["russian", "english", "chinese"]:
            print(f"  🎙 [{lang}] {phrases[lang]}")
            translator.voice.text_to_voice(phrases[lang], language=lang, play=True)

    # ── voice translate файл [to=lang] ──
    elif sub_cmd == "translate":
        audio_file = sub_args.split()[0] if sub_args else ""
        if not audio_file or not os.path.exists(audio_file):
            print(f"{C['error']}Укажите путь к аудиофайлу: v translate файл.wav [to=lang]{C['reset']}")
            return
        target_lang = "english"
        for p in sub_args.split():
            if p.startswith("to="):
                t = p.split("=")[1]
                target_lang = lang_aliases.get(t, t)
        translator.voice_to_voice(audio_file, target_language=target_lang)

    else:
        print(f"{C['info']}ГОЛОСОВЫЕ КОМАНДЫ (Whisper + TTS):{C['reset']}")
        print(f"  voice record [sec=10] [lang]       — запись с микрофона")
        print(f"  voice speak ru ТЕКСТ                — озвучить на русском")
        print(f"  voice speak en TEXT                 — озвучить на английском")
        print(f"  voice speak zh 文本                 — озвучить на китайском")
        print(f"  voice demo                          — демо на всех 3 языках")
        print(f"  voice translate файл.wav [to=en]    — голосовой перевод")


def handle_image(translator: AeonTranslator, args: str):
    """Обрабатывает команды генерации изображений."""
    if not translator.flux.available:
        print(f"{C['error']}Flux 2 API ключ не настроен в .env{C['reset']}")
        return

    sub_parts = args.split(maxsplit=1)
    sub_cmd = sub_parts[0].lower() if sub_parts else ""

    if sub_cmd == "emotion":
        text = sub_parts[1] if len(sub_parts) > 1 else ""
        if not text:
            print(f"{C['error']}Опишите эмоцию{C['reset']}")
            return
        result = translator.emotion_to_image(text)
        print_image_result(result)

    elif sub_cmd == "code" and len(sub_parts) > 1:
        result = translator.code_to_image(sub_parts[1])
        print_image_result(result)

    else:
        # По умолчанию: текст → изображение
        style = "realistic"
        text = args
        for p in args.split():
            if p.startswith("style="):
                style = p.split("=")[1]
                text = args.replace(p, "").strip()
        if not text:
            print(f"{C['error']}Опишите, что нарисовать{C['reset']}")
            return
        result = translator.text_to_image(text, style=style)
        print_image_result(result)


def print_image_result(result: dict):
    if result.get("error"):
        print(f"\n{C['error']}Ошибка: {result['error']}{C['reset']}")
        return
    print(f"\n{C['success']}✓ ИЗОБРАЖЕНИЕ СГЕНЕРИРОВАНО{C['reset']}")
    print(f"  Статус: {result.get('status', '?')}")
    paths = result.get("saved_paths", [])
    if paths:
        for p in paths:
            print(f"  Файл: {p}")
            # Открыть в просмотрщике
            try:
                os.startfile(p)
            except Exception:
                pass
    elif result.get("images"):
        for url in result["images"][:3]:
            if isinstance(url, str) and len(url) < 500:
                print(f"  URL: {url}")
    if result.get("cost"):
        print(f"  Стоимость: {result['cost']}")
    if result.get("runtime"):
        print(f"  Время: {result['runtime']:.1f}с")


def run_demo(translator: AeonTranslator):
    """Полная демонстрация возможностей."""
    print(f"\n{C['title']}{'='*60}")
    print("🎬 ДЕМОНСТРАЦИЯ AEON v2.0")
    print(f"{'='*60}{C['reset']}")

    # Демо 1: Русский → Английский
    print(f"\n{C['info']}📌 ДЕМО 1: Русский → Английский (LLM){C['reset']}")
    result = translator.translate(
        "Я хочу понять, как устроен мир",
        source_form="text", source_language="russian",
        target_form="text", target_language="english"
    )
    print(f"🇷🇺 Я хочу понять, как устроен мир")
    print(f"🇬🇧 {result['target']['content'][:200]}")
    print(f"   LLM: {'✅' if result.get('llm_powered') else '⚠️'}")

    # Демо 2: Английский → Китайский
    print(f"\n{C['info']}📌 ДЕМО 2: Английский → Китайский (LLM){C['reset']}")
    result = translator.translate(
        "Artificial intelligence should help humanity",
        source_form="text", source_language="english",
        target_form="text", target_language="chinese"
    )
    print(f"🇬🇧 Artificial intelligence should help humanity")
    print(f"🇨🇳 {result['target']['content'][:200]}")

    # Демо 3: Мысль → Python-код (LLM codegen)
    print(f"\n{C['info']}📌 ДЕМО 3: Мысль → Python-код (LLM){C['reset']}")
    result = translator.translate(
        "Система, которая учится на ошибках и становится умнее с каждым днём",
        source_form="text", source_language="russian",
        target_form="code", target_language="python"
    )
    print(f"🧠 Система, которая учится на ошибках...")
    print(f"💻 Python:\n{result['target']['content'][:400]}...")

    # Демо 4: Мост разумов (LLM)
    print(f"\n{C['info']}📌 ДЕМО 4: Мост между разумами (LLM){C['reset']}")
    bridge = translator.bridge_minds(
        {"content": "Машины должны помогать людям", "language": "russian"},
        {"content": "AI should serve humanity", "language": "english"}
    )
    print(f"🇷🇺 Машины должны помогать людям")
    print(f"🇬🇧 AI should serve humanity")
    print(f"{'✅' if bridge['minds_connected'] else '❌'} Понимание")
    if bridge.get('similarity'):
        print(f"   Сходство: {bridge['similarity']:.0%}")
    if bridge.get('explanation'):
        print(f"   {bridge['explanation']}")
    print(f"   LLM: {'✅' if bridge.get('llm_powered') else '⚠️'}")

    # Демо 5: Эмоция → Визуализация
    print(f"\n{C['info']}📌 ДЕМО 5: Эмоция → Визуализация{C['reset']}")
    result = translator.translate(
        "Я чувствую вдохновение и радость от познания нового",
        source_form="emotion", target_form="visualization"
    )
    print(f"💖 Я чувствую вдохновение и радость от познания нового")
    print(result['target']['content'][:400])

    # Демо 6: Изображение (опционально)
    if translator.flux.available:
        print(f"\n{C['info']}📌 ДЕМО 6: Идея → Изображение (Flux 2){C['reset']}")
        print("Генерация изображения 'A bridge of light between different worlds'...")
        img_result = translator.text_to_image(
            "A bridge of light connecting different worlds together",
            style="futuristic, ethereal"
        )
        print_image_result(img_result)
    else:
        print(f"\n{C['dim']}📌 ДЕМО 6: Изображение — пропущено (нет Flux API ключа){C['reset']}")

    # Демо 7: Голос (опционально) — на 3 языках
    if translator.voice.tts.available:
        print(f"\n{C['info']}📌 ДЕМО 7: Голос на 3 языках (TTS){C['reset']}")
        phrases = {
            "russian": "Смысл един. Различаются только формы.",
            "english": "Meaning is one. Only the forms differ.",
            "chinese": "意义是统一的，不同的只是形式。"
        }
        for lang in ["russian", "english", "chinese"]:
            print(f"🔊 [{lang}] {phrases[lang]}")
            translator.voice.text_to_voice(phrases[lang], language=lang, play=True)
    else:
        print(f"\n{C['dim']}📌 ДЕМО 7: Голос — пропущено (нет TTS){C['reset']}")

    print(f"\n{C['success']}✅ Демонстрация завершена!{C['reset']}")
    show_stats(translator)


if __name__ == "__main__":
    run_cli()
