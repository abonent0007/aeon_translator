# 🌌 AEON v3.0 — Универсальный Транслятор Смысла

**Реальные эмбеддинги. Явная семантика. Защита от галлюцинаций.**

---

## Оглавление

1. [Концепция](#1-концепция)
2. [Архитектура](#2-архитектура)
3. [Схема работы](#3-схема-работы)
4. [Модули](#4-модули)
5. [Установка](#5-установка)
6. [Запуск](#6-запуск)
7. [CLI-команды](#7-cli-команды)
8. [Python API](#8-python-api)
9. [Конфигурация](#9-конфигурация)
10. [Модальности](#10-модальности)
11. [Формат .aeon](#11-формат-aeon)
12. [Зависимости](#12-зависимости)
13. [Статус и тестирование](#13-статус-и-тестирование)

---

## 1. Концепция

Aeon — **семантический процессор**. Вместо перевода слов — перевод **значения**:

```
Русский текст  ←→  English text  ←→  中文文本
Эмоция         ←→  Код (Python/JS)
Голос          ←→  Изображение
Текст          ←→  .aeon (бинарный смысловой файл)
```

**«Смысл един. Различаются только формы.»**

### Аксиомы

| Аксиома | Суть |
|---------|------|
| `identity` | Всё есть то, что оно есть. A = A. |
| `relation` | Ничто не существует изолированно. |
| `transformation` | Любая сущность может быть преобразована. |
| `intention` | Код должен выражать намерение, а не механику. |
| `symbiosis` | Язык — мост между разумами. |
| `compression` | Максимум смысла в минимуме символов. |
| `beauty` | Красивый код — понятный код. |

### Что нового в v3.0

| Возможность | v2.0 | v3.0 |
|-------------|:----:|:----:|
| Эмбеддинги | 16D ручные примитивы | **384D MiniLM** (50+ языков, реальное смысловое пространство) |
| Семантическая структура | intent + domain | **сущности, роли, отношения, evidence** |
| Интерпретируемость | — | **цепочка рассуждений, декомпозиция уверенности** |
| Кросс-языковой мост | LLM-сравнение | **LaBSE-эмбеддинги** + LLM-верификация |
| Защита от галлюцинаций | — | **consistency check + fact grounding** |
| Формат файла | — | **.aeon** (2.2 КБ/атом, бинарный, интерпретируемый) |
| Семантический поиск | — | **cosine similarity по эмбеддингам** |

---

## 2. Архитектура

```
┌──────────────────────────────────────────────────────────────────┐
│                        AEON v3.0                                  │
│                Семантический процессор смысла                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ┌──────────┐   ┌──────────────┐   ┌──────────────────┐        │
│   │  INPUT   │   │  EXTRACTOR   │   │    GENERATOR     │        │
│   │  (form)  │──▶│  (semantic)  │──▶│    (expression)  │──▶ OUTPUT│
│   └──────────┘   └──────────────┘   └──────────────────┘        │
│        │                │                      │                  │
│        ▼                ▼                      ▼                  │
│   ┌─────────┐     ┌──────────┐          ┌──────────────┐         │
│   │  text   │     │ LLM+Emb  │          │  LLM+Emb     │         │
│   │  code   │     │  768D    │          │              │         │
│   │ emotion │     │          │          │  text/code   │         │
│   │  audio  │     │ Semantic │          │  voice/image │         │
│   │         │     │  Atom    │          │  .aeon/visual│         │
│   └─────────┘     │  v3.0    │          └──────────────┘         │
│                   └──────────┘                                    │
│                        │                                          │
│                        ▼                                          │
│   ┌──────────────────────────────────────────────────────┐       │
│   │                 ENGINE MODULES v3.0                    │       │
│   ├──────────────┬──────────────┬────────────────────────┤       │
│   │ DeepSeek LLM │  MiniLM 384D │  Verification Engine   │       │
│   │ (перевод,    │  (эмбеддинги)│  (consistency+ground)  │       │
│   │  код, смысл) │              │                        │       │
│   ├──────────────┼──────────────┼────────────────────────┤       │
│   │  Whisper STT │  Edge/Piper   │  Flux 2 (изображения) │       │
│   │  (голос→текст)│  TTS (3 яз.) │                        │       │
│   ├──────────────┼──────────────┼────────────────────────┤       │
│   │  .aeon Format│  Bridge v3   │  Semantic Search       │       │
│   │  (бинарный)  │  (3 метода)  │  (cosine similarity)   │       │
│   └──────────────┴──────────────┴────────────────────────┘       │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### Приоритет движков

```
LLM (DeepSeek) → rule-based fallback     # извлечение + генерация
MiniLM 384D    → 16D примитивы           # эмбеддинги
Edge TTS       → Piper TTS → системный   # синтез речи
```

---

## 3. Схема работы

### Цепочка трансляции (translate)

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐     ┌──────────────┐
│   ИСТОЧНИК   │     │   ИЗВЛЕЧЕНИЕ    │     │   ГЕНЕРАЦИЯ      │     │    ЦЕЛЬ      │
│   (source)   │ ──▶ │   СМЫСЛА        │ ──▶ │   ВЫРАЖЕНИЯ      │ ──▶ │   (target)   │
│              │     │                 │     │                  │     │              │
│  text/ru     │     │  SemanticAtom   │     │  text/en         │     │ "Hello"      │
│  "Привет"    │     │  v3.0:          │     │                  │     │              │
│              │     │  • 384D emb     │     │                  │     │              │
│              │     │  • entities     │     │                  │     │              │
│              │     │  • roles        │     │                  │     │              │
│              │     │  • evidence     │     │                  │     │              │
└──────────────┘     └─────────────────┘     └──────────────────┘     └──────────────┘
        │                                               │
        └─────────── verify (опционально) ──────────────┘
                    consistency + fact grounding
```

### Цепочка моста разумов v3 (bridge)

```
┌──────────────┐          ┌──────────────┐
│   РАЗУМ А    │          │   РАЗУМ B    │
└──────┬───────┘          └──────┬───────┘
       │                         │
       ▼                         ▼
  ┌─────────┐             ┌─────────┐
  │ MiniLM  │             │ MiniLM  │
  │ 384D    │             │ 384D    │
  └────┬────┘             └────┬────┘
       │                       │
       └───────┬───────────────┘
               ▼
    ┌─────────────────────┐
    │  3 метода сравнения: │
    │  1. LaBSE cosine    │
    │  2. LLM semantic    │
    │  3. Cross-lingual   │
    │     verification    │
    └─────────┬───────────┘
              ▼
    similarity: 0.95
    "Глубокое понимание"
```

### Семантический атом v3.0

```
┌─────────────────────────────────────────────────────┐
│                SEMANTIC ATOM v3.0                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ meaning_hash: "a3f2..."                      │   │
│  │ source_text: "AI helps doctors"              │   │
│  │                                               │   │
│  │ ── РЕАЛЬНЫЙ ЭМБЕДДИНГ ──                     │   │
│  │ 384D вектор (MiniLM, 50+ языков)              │   │
│  │                                               │   │
│  │ ── ИНТЕРПРЕТИРУЕМАЯ СТРУКТУРА ──              │   │
│  │ intent: "statement"   domain: "science"       │   │
│  │                                               │   │
│  │ ENTITIES:                                     │   │
│  │  • AI (concept) [agent]                       │   │
│  │  • doctors (person) [patient]                 │   │
│  │  • diseases (concept) [goal]                  │   │
│  │                                               │   │
│  │ ROLES: agent=AI, patient=doctors, goal=diseases│   │
│  │                                               │   │
│  │ ── ИНТЕРПРЕТИРУЕМОСТЬ ──                      │   │
│  │ explanation_chain: 5 шагов рассуждения         │   │
│  │ evidence: 3 цитаты из текста                   │   │
│  │ confidence_breakdown:                          │   │
│  │   intent: 95%, domain: 90%,                    │   │
│  │   entities: 85%, roles: 80%                    │   │
│  │                                               │   │
│  │ ── ЗАЩИТА ОТ ГАЛЛЮЦИНАЦИЙ ──                   │   │
│  │ consistency_score: 1.0                         │   │
│  │ hallucination_risk: 0.0                        │   │
│  │ fact_grounded: true                            │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## 4. Модули

| Файл | Назначение | Движок |
|------|------------|--------|
| `aeon/core.py` | Аксиомы, базовые типы (`Thought`, `Flow`, `Concept`) | — |
| `aeon/semantic_atom.py` | Семантический атом v3: 384D эмбеддинг + entities + roles + evidence | — |
| `aeon/embeddings.py` | **НОВОЕ:** кросс-языковые эмбеддинги | **MiniLM 384D** |
| `aeon/llm_client.py` | DeepSeek API: извлечение, перевод, код, сравнение, промпты | **DeepSeek LLM** |
| `aeon/extractor.py` | Извлекатель v3: текст → 384D + entities + roles + explanation | LLM + Embeddings |
| `aeon/generator.py` | Генератор: атом → текст/код/визуализация/prompt | LLM + rule-based |
| `aeon/verification.py` | **НОВОЕ:** защита от галлюцинаций | LLM + Embeddings |
| `aeon/translator.py` | Оркестратор: все модальности + bridge + search + .aeon | — |
| `aeon/aeon_format.py` | **НОВОЕ:** бинарный .aeon формат (save/load/compare) | — |
| `aeon/voice.py` | Голос: Whisper STT + MultiVoiceTTS (ru/en/zh) | **Whisper** + **Edge TTS** |
| `aeon/image_gen.py` | Flux 2 генерация изображений | **Flux 2 API** |
| `aeon/cli.py` | Консольный интерфейс (translate, code, bridge, voice, image, verify, search, save, explain) | — |
| `aeon/demo.py` | Интерактивная демонстрация (6 частей) | — |

---

## 5. Установка

### Требования

- **Python 3.8+**
- Windows 10/11, Linux или macOS
- ~3 ГБ места (MiniLM + Whisper + Torch)

### Быстрый старт

```bash
cd aeon_translator
pip install -r requirements.txt
```

### Проверка

```bash
python -c "from aeon import AeonTranslator; t = AeonTranslator()"
```

Ожидаемый вывод:

```
============================================================
🌌 AEON v3.0 — СТАТУС МОДУЛЕЙ
============================================================
  LLM (DeepSeek):  ✅ ONLINE
  Embeddings:      ✅ 384D
  Verification:    ✅ ACTIVE
  Whisper STT:     ✅ AVAILABLE
  TTS (ru/en/zh):  ✅ AVAILABLE
  Flux 2 Images:   ✅ AVAILABLE
  .aeon Format:    ✅ READY
============================================================
```

---

## 6. Запуск

| Команда | Описание |
|---------|----------|
| `python -m aeon.cli` | Интерактивный CLI |
| `python aeon/demo.py` | Демонстрация (6 частей) |
| `run_aeon.bat` | Меню (Windows) |

### Структура demo.py

1. **Базовые концепты** — аксиомы, Thought, Flow, Concept
2. **Транслятор** — перевод ru→en→zh, кодогенерация
3. **Мост разумов** — LaBSE + LLM сравнение
4. **Мультимодальность** — изображения, голос (ru/en/zh)
5. **v3 Enhanced** — интерпретация, верификация, кросс-языковой мост, .aeon формат

---

## 7. CLI-команды

### Перевод (translate)

```bash
aeon> t Привет мир to=english
aeon> t "Hello world" to=chinese
aeon> t "I feel joy" form=visualization
```

### Кодогенерация (code)

```bash
aeon> c Сортировка массива пузырьком lang=python
aeon> c "REST API for users" lang=javascript
```

### Мост разумов (bridge)

```bash
aeon> b Машины должны помогать людям | AI should serve humanity
# → similarity: 1.0, connected: True, methods: [labse, llm, verification]
```

### Голос (voice) — Whisper + TTS

```bash
aeon> v record                      # запись → текст
aeon> v record sec=5 ru             # 5 сек, подсказка: русский
aeon> v speak ru Привет             # русский голос
aeon> v speak en Hello              # английский голос
aeon> v speak zh 你好              # китайский голос
aeon> v demo                        # демо на всех 3 языках
aeon> v translate речь.wav to=en    # голосовой перевод
```

### Верификация (verify) — защита от галлюцинаций

```bash
aeon> vf Земля вращается вокруг Солнца
# → consistency + fact grounding → risk 43%, verdict: suspect
```

### Интерпретация (explain) — полная прозрачность

```bash
aeon> x Искусственный интеллект помогает врачам
# → entities, roles, evidence, explanation_chain, confidence_breakdown
```

### .aeon формат (save / compare)

```bash
aeon> save Смысл един path=meaning.aeon
aeon> compare meaning1.aeon meaning2.aeon
# → distance, intent_match, domain_match, common_entities, verdict
```

### Семантический поиск (search)

```bash
aeon> search машинное обучение | deep learning | кошка | neural networks | пицца
# → ranked by cosine similarity
```

### Изображения (image) — Flux 2

```bash
aeon> img "Futuristic city at sunset" style=cyberpunk
aeon> img emotion Радость открытия
```

### Визуализация (viz)

```bash
aeon> viz "Съешь еще этих мягких французских булок"
```

### Прочее

```bash
aeon> axioms      # 7 аксиом
aeon> stats       # статистика + статус всех модулей
aeon> demo        # полная демонстрация
aeon> help        # справка
aeon> exit        # выход
```

---

## 8. Python API

```python
from aeon import AeonTranslator

t = AeonTranslator()

# ── Перевод ──
r = t.translate("Привет мир", source_language="russian", target_language="english")
print(r['target']['content'])  # → "Hello world"

# ── Кодогенерация ──
r = t.translate("Сортировка пузырьком", target_form="code", target_language="python")
print(r['target']['content'])  # → def bubble_sort(arr): ...

# ── Мост разумов v3 ──
bridge = t.bridge_minds(
    {"content": "AI helps people", "language": "english"},
    {"content": "Искусственный интеллект помогает людям", "language": "russian"}
)
print(bridge['similarity'])         # → 1.0
print(bridge['methods'].keys())     # → ['labse', 'llm', 'cross_lingual_verification']

# ── Верификация ──
r = t.translate("The sky is blue", target_language="russian", verify=True)
v = r['metadata']['verification']
print(v['hallucination_risk'])      # → 0.43
print(v['overall_verdict'])         # → "suspect"

# ── Интерпретация ──
atom = t.extractor.extract_from_text("AI helps doctors diagnose diseases")
print(atom.explain())
# → entities, roles, explanation_chain, evidence, confidence_breakdown

# ── .aeon формат ──
t.save_aeon("Hello world", "hello.aeon")
atoms = t.load_aeon("hello.aeon")
print(len(atoms[0].embedding))      # → 384

# ── Семантический поиск ──
results = t.semantic_search("machine learning",
    ["deep learning", "cat", "neural networks", "pizza"])
# → [{text: "neural networks", score: 0.679}, ...]

# ── Кросс-языковое сходство ──
sim = t.embeddings.cross_lingual_similarity(
    "Привет мир", "russian", "Hello world", "english")
print(sim)  # → 0.678

# ── Изображение ──
img = t.text_to_image("A futuristic city", style="cyberpunk")

# ── Голос ──
t.speak_translation("Смысл един", target_language="russian")
t.voice_to_voice("speech.wav", target_language="english")
```

### Формы (source_form / target_form)

| Форма | Описание |
|-------|----------|
| `text` | Естественный язык |
| `code` | Python / JavaScript |
| `emotion` | Описание эмоции |
| `visualization` | ASCII-визуализация атома |
| `image` | Flux 2 генерация |
| `voice` | Синтез речи (TTS) |
| `audio` | Распознавание речи (STT) |
| `aeon` | Бинарный .aeon файл |

### Языки

`russian`, `english`, `chinese`, `japanese`, `german`, `french`, `spanish`, `auto`

---

## 9. Конфигурация

Файл `.env`:

```env
# DeepSeek LLM (перевод, код, смысл, верификация)
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# Flux 2 (генерация изображений)
FLUX_API_KEY=sk-xxx
FLUX_API_URL=https://api.gen-api.ru/api/v1/networks/flux-2
```

Без API-ключей: **rule-based fallback** (базовый перевод по шаблонам, без верификации, без изображений).

---

## 10. Модальности

| Вход | Выход | Движок |
|------|-------|--------|
| Текст (ru) | Текст (en/zh/...) | DeepSeek LLM |
| Текст | Python / JavaScript | DeepSeek LLM |
| Эмоция | Визуализация | 16D примитивы + 384D emb |
| Текст | Изображение | LLM-промпт → Flux 2 |
| Голос (.wav) | Текст | Whisper STT |
| Текст | Голос (.mp3) | Edge TTS → Piper → системный |
| Голос (ru) | Голос (en) | Whisper → LLM → TTS |
| Текст А + Текст Б | similarity score | MiniLM + LLM |
| Текст | .aeon файл | AeonFormat (бинарный) |
| Запрос + кандидаты | Ранжированный список | cosine similarity |

---

## 11. Формат .aeon

Бинарный формат для хранения семантических атомов.

```
┌──────────────────────────────────────────────┐
│ HEADER (64 байта)                             │
│  magic: "AEON"  version: 1                    │
│  emb_dim: 384   prim_dim: 16                  │
│  atom_count: N  edge_count: M                 │
├──────────────────────────────────────────────┤
│ ATOM (переменная длина)                        │
│  hash (16B) + embedding (384×2B)              │
│  + prim_vec (16×2B) + intent/domain/lang      │
│  + entities (JSON) + evidence (JSON)          │
│  + explanation (JSON) + confidence (JSON)     │
│  + hallucination metrics                      │
├──────────────────────────────────────────────┤
│ EDGE (переменная длина)                        │
│  src_hash + tgt_hash + rel_type + strength    │
├──────────────────────────────────────────────┤
│ FOOTER: SHA256 + "EONA"                       │
└──────────────────────────────────────────────┘
```

**Характеристики:**
- ~2.2 КБ на атом (с 384D эмбеддингом)
- В ~1000× компактнее LLM-весов
- Полностью интерпретируемый (entities, evidence, explanation)
- Сравнение двух .aeon: `distance`, `intent_match`, `common_entities`

---

## 12. Зависимости

```
numpy>=1.24.0              # векторы
colorama>=0.4.6            # цветной CLI
rich>=13.0.0               # форматирование
pyyaml>=6.0                # конфигурация
openai>=1.0.0              # DeepSeek API
python-dotenv>=1.0.0       # .env загрузка
requests>=2.28.0           # HTTP (Flux API)
sounddevice>=0.4.6         # запись/воспроизведение
soundfile>=0.12.0          # аудиофайлы
edge-tts>=6.0.0            # нейро TTS
openai-whisper             # STT (локально)
sentence-transformers>=2.2 # эмбеддинги MiniLM
```

```bash
pip install -r requirements.txt
```

---

## 13. Статус и тестирование

### Статус модулей (проверено)

| Модуль | Статус |
|--------|--------|
| LLM (DeepSeek) | ✅ ONLINE |
| Embeddings (MiniLM 384D) | ✅ LOADED |
| Verification Engine | ✅ ACTIVE |
| Whisper STT | ✅ AVAILABLE |
| TTS (ru/en/zh) | ✅ AVAILABLE |
| Flux 2 Images | ✅ AVAILABLE (нужны кредиты) |
| .aeon Format | ✅ READY |
| Rule-based fallback | ✅ Всегда |

### Пройдено тестов: 23/23

| Группа | Тестов |
|--------|:------:|
| translate (ru→en, en→zh, auto→ru) | 3/3 |
| code (python, javascript) | 2/2 |
| bridge (same, different) | 2/2 |
| visualization (text, emotion, code) | 3/3 |
| verification (verify on, verify+code) | 2/2 |
| .aeon format (save, load, compare) | 4/4 |
| semantic search | 1/1 |
| interpretation (explain text, emotion) | 2/2 |
| image (prompt generation) | 1/1 |
| voice (status) | 1/1 |
| stats + axioms | 2/2 |

---

> *«Смысл един. Различаются только формы.»*
>
> *«Одна голова хорошо, а две — это хорошо хорошо»*
> *«Two heads are better than one»*
> *«一个好汉三个帮»*
>
> Все говорят об одном. Потому что **СМЫСЛ един.** 🌌
