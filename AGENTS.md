# AEON v4.0 «Deep Analyst» — Project Guide

## Overview
Semantic processor: переводит смысл между формами (текст/код/эмоция/голос/изображение)
с верификацией, entity linking и анализом древних текстов.
Статус: **Фаза 0 ✅, Фаза 1 ✅, **Фаза 2 ✅ complete (2.0–2.6 + 2.7 real-API
validation — см. «Phase 2 closure»)**; Фаза 3 — 3.1 ✅ (`.aeon v2`), 3.2 ✅
(morph_v1), 3.3 ✅ (gold-standard), 3.5 ✅ (variant readings); **midpoint
checkpoint — `docs/phase3_checkpoint.md`; следующий — 3.4 scoping (Plan Mode)**.**

## Architecture (Фаза 1)
```
текст ──► MeaningExtractor (LLM-структура + rule fallback)
      ──► SemanticAtom (+ фрагменты: is_fragment / completeness / needs_attention)
      ──► Entity Linking: Wiki data (search→fetch; cache 7д; merged-QID healing)
      │                   └─► external_ids: wikidata / pleiades(P1584) / trismegistos(P11651)
      ──► Verification 2.0 (verify_mode: off|basic|full):
      │     Detective (grounding/цитаты) · Expert (факт-чек) · Logician (coherence)
      │     └─► Aggregator: CVI + calibrated abstention (≥0.50, иначе «Я не знаю»)
      ──► Generator / .aeon v1 (reasoning trace — в v2, Фаза 3)
```

## Language Pack Architecture (Фаза 2)
Контракт (`aeon/language/base.py`): ABC `LanguagePack` — `iso_code`,
`display_name`, `period` (BCE — отрицательные), `direction`,
`special_tokens` {lacuna, editorial} (значение — строка ИЛИ список вариантов),
`prompts` {extract, verify, reconstruct}, `dictionaries`, `unicode_ranges`;
методы: `detect_markers` [abstract], `normalize` [NFC default], `is_fragment`,
`detect_heuristic` [default 0; бонус к Unicode-hits для общих алфавитов,
напр. ASCII-латынь], `validate` (fail-fast контракт).

Реестр (`aeon/language/registry.py`): `register` — eager-регистрация фабрики,
lazy-инстанциация + validate при первом `get` (инстанс валидируется сразу);
`force=True` — осознанный override; `get` — KeyError со списком; `list_available`
(sorted); `detect` — двухфазно: (1) unicode-ranges (max-hits — алфавит решает),
(2) при равенстве/отсутствии hits — `detect_heuristic` (default 0; эволюция
контракта в 2.2); **tie-break детерминирован (алфавитный iso_code) +
событие `detect_ambiguous`**; `clear` — тесты.

Как добавить пак: подкласс `LanguagePack` (реализовать `detect_markers`) →
`registry.register(PackClass)`; builtin-паки регистрируются в
`aeon/language/__init__.py` (класс, инстанциация ленива).

Политика нормализации (refinement 2.0 №2): нормализуется только
**pipeline-вход**; оригинальный текст пользователя сохраняется в
`result["source"]["content"]` (см. тест `test_translate_original_content_preserved`).

Приоритет маркеров: `pack.special_tokens` — приоритетный источник;
`semantic_atom.LACUNA_MARKERS` — fallback, когда pack=None (интеграция
в extractor — шаги 2.3+).

## Ancient Greek Pack (шаг 2.1)
`aeon/language/grc.py` — `grc` (Ancient Greek, period −800..600).

Конвенции маркеров (подмножество Leiden/SIG): `lacuna` — `[...] […] [lacuna]
[---]`; **`supplement` — контекстное правило (стоп-точка 2.1 №1)**: скобки с
буквами (`[Ἀθῆναι]`, `[Ἀριστ]είδης`) → supplement; скобки с точками/тире →
lacuna; `editorial` — `<...> <*>`; `deletion` — `{...}`; `uncertain` —
`(...) [...?]`.

Нормализация (стоп-точка 2.1 №2, решения): NFC (дыхания/диакритика
СОХРАНЯЮТСЯ — семантичны: ἡ ≠ ἠ); конечная сигма ς **не** унифицируется с σ;
iota subscript (ᾳ/ῃ/ῳ) **не** разворачивается в adscript. Обоснование —
Unicode-стандарт + практика изданий Perseus/TLG (стандартная орфография);
поисковые унификации — отдельный слой Ф3.

Промпты (`extract`/`verify`/`reconstruct`, ≤30 строк): явно ссылаются на
маркеры; `reconstruct` — 2–4 гипотезы + обязательный путь
`no_reconstruction_possible` (max confidence < 0.5).

Ограничения: морфологии нет (Ф3, Morpheus — интерфейс-хук); древний и
новогреческий по codepoints не различаем (кандидат от `detect`;
тест-документация `test_detect_modern_greek_documented_limitation`).

Эталонные тексты: `examples/greek/` — 5 фрагментов (Plato Apologia,
Homer Il. 1.1–7, надпись с лакунами, папирус с лакунами, Sappho fr. 31)
+ `LICENSE.md` (public domain; копии оцифровок Perseus/PHI сознательно
не использовались — стоп-точка 2.1 №4; per-file атрибуция — Ф2.6).

## Latin Pack (шаг 2.2)
`aeon/language/la.py` — `la` (Latin, period −200..1800; Classical vs
Medieval/Neo-Latin не различаем).

Маркеры: `lacuna`/`editorial`/`deletion`/`uncertain` — как в grc;
**`crux` `†...†` — ОТДЕЛЬНЫЙ kind (стоп-точка 2.2 №2)**: locus desperatus —
текст есть, но испорчен (≠ lacuna «утрачено физически», ≠ editorial
«добавлено редактором»); `[буквы]` → supplement (контекстное правило).

Нормализация (стоп-точка 2.2 №1, решение): NFC; **j/v и i/u НЕ сводятся** —
текст сохраняется как в источнике (OCT/Teubner/Loeb печатают классику с
осмысленным u/v-различением; свёртка — поисковый слой Ф3, как ς/σ в grc);
макроны (ā ē ī ō ū) СОХРАНЯЮТСЯ (долгота/метрика); регистр не трогаем.

Детекция (algorithm, refinement 2.2 №4 — двухфазно):
1) Unicode-ranges: если есть hits — побеждает max-hits (алфавит решает);
2) при равенстве/отсутствии — `detect_heuristic` паков (common alphabet).
`la`-эвристика: **УНИКАЛЬНЫЕ** служебные слова (1.0) + падежные окончания
(0.5), порог ≥2: «Gallia est omnis divisa…» → `la`, «hello world» → `None`,
«in vitro»/«et al.» → `None` (повторы не считаются). Порог/веса — хардкод
Classical (Medieval/Neo-Latin может underdetect; вынос в конфиг — backlog).
Алгоритм и лимитации: AGENTS → Language Pack Architecture.

Промпты (≤30 строк): verify — lacuna И `†word†` → 
`unverifiable_due_to_missing_data` (НЕ contradicted); reconstruct — cruces
восстанавливаются только с внешними свидетельствами, иначе
`no_reconstruction_possible`.

Тексты: `examples/latin/` — Caesar BG 1.1, Cicero Cat. 1.1, Vergil Aen. 1.1–7,
CIL-образец (лакуны/восстановления/†), Vulgata Gen. 1.1 + `LICENSE.md`
(PD; макроны Vulgata — учебная конвенция AEON; CIL/EDCS-копии не делались).

## Fragment Hypothesis Engine (шаг 2.3)
Пакет `aeon/fragments/`: `hypothesis.py` (Hypothesis / NoReconstruction /
ReconstructionResult — все JSON-сериализуемы; .aeon v2 — Ф3), `ranking.py`
(rank/cap/drop_contradicted), `engine.py` (оркестратор).

Поток `FragmentHypothesisEngine.reconstruct(atom, pack=None)`:
1. маркеры: `pack.detect_markers` (приоритет) → fallback
   `semantic_atom.LACUNA_MARKERS` (pack=None);
2. `fragment_density = markers_count / max(len(text), 1)` — **не влияет на
   is_fragment**, только результат/логирование (и кандидат на приоритизацию);
   конфиг `AEON_FRAGMENT_DENSITY_THRESHOLD` (default 0.005);
3. только-cruces → `no_reconstruction_possible(reason=
   "cruces_without_external_evidence")` без LLM (терминальный вердикт +
   reason — структурированный сигнал внешним источникам, Ф2.6; в СМЕШАННОМ
   тексте lacunae реконструируются, cruces исключаются из `markers_addressed`);
4. LLM (temperature **0.0** — детерминизм, насколько позволяет провайдер):
   pack-промпт `reconstruct` (или DEFAULT, ≤30 строк) → 2–4 гипотезы;
   серверная защита: cap=4, `max(confidence) < 0.75`
   (`AEON_FRAGMENT_MIN_CONFIDENCE`) → `reason="max_confidence_below_threshold"`
   (реконструкция — акт СОЗДАНИЯ: цена ошибки выше, порог выше abstention 0.50);
5. **верификация ОБЯЗАТЕЛЬНА** (curator fix 2.3): каждая гипотеза → Детектив
   (N вызовов), claim = «кандидат согласуется с сохранившимся контекстом»
   (exact-quote утраченного невозможен); **проходит ТОЛЬКО `grounded`** —
   neutral/abstained/contradicted отбрасываются; пусто →
   `all_contradicted` (все отвергнуты) или `no_verified_hypotheses` (прочие).
   Отключение верификации запрещено: `FragmentsConfig` → ConfigError
   (`AEON_FRAGMENT_VERIFY_HYPOTHESES=0`).
Остальные reason: `no_markers`, `llm_unavailable`, `llm_parse_error`,
`llm_declined` (**честный отказ LLM** — JSON `status=no_reconstruction_possible`,
НЕ ошибка: при gold-real считается отдельно от failures), `llm_returned_none`
(пустой ответ без объяснения).

Флаги: `translate(..., reconstruct=False)` (default off — backward compat
Ф2.2; при `True` и `atom.is_fragment` результат в
`metadata["reconstruction"]`); demo `--reconstruct`.
Сериализация: `to_dict()` JSON-совместим; хранение в `.aeon v2` — Ф3
(v1 формат не трогали).
Варианты чтения (contested readings ≠ лакуны) — backlog Ф2.4+ (Sappho идёт
обычным fragment-путём; demo-мок использует реальное восстановление ст. 13).

Конфиг: `CONFIG.fragments` (`AEON_FRAGMENT_MAX_HYPOTHESES=4`,
`AEON_FRAGMENT_MIN_CONFIDENCE=0.75`, `AEON_FRAGMENT_DENSITY_THRESHOLD=0.005`,
`AEON_FRAGMENT_VERIFY_HYPOTHESES=1` — только True).

## Linguistic Layers (шаг 2.4)
Пакет `aeon/linguistics/`: `base.py` (ABC `LinguisticLayer`, `Finding`,
`LayerResult`, `LayerContext`), `prompts.py` (промпты слоёв — ЗДЕСЬ, не в
паках), четыре слоя (`lexical`/`syntactic`/`semantic`/`pragmatic`),
`orchestrator.py` (`ChainOfLinguistics`).

Порядок фиксирован: lexical → syntactic → semantic → pragmatic.
Зависимости строгие (`ConfigError`): syntactic→lexical, semantic→syntactic,
pragmatic→semantic; lexical — standalone. Alias `"all"` — все четыре.
Halt: confidence слоя < `CONFIG.linguistics.layer_min_confidence` (0.3) →
`halted_at_<layer>`, частичный результат сохраняется; `llm_calls` суммируется.
Противоречия слоёв (стоп-точка №2, вариант B): детектируются по
span+kind-классу (`pos_tag`/`role`), логируются событием
`layer_contradiction`, цепочка продолжается с понижением confidence ×0.7;
LLM-разрешение (+1 вызов, вариант C) — backlog.

Промпты ≤30 строк, temp 0.0, strict JSON. Языковые hints — хук
`pack.linguistic_hints(layer)` (grc: оптатив/средний залог/двойственное;
la: аблатив/герундий/депоненты); промпты языково-неспецифичны.
Handoff-контракт: `lexical` → {lemmas, morphology}; `syntactic` →
{clauses, deviations}; `semantic` → {propositions, ambiguities};
`pragmatic` → {speech_acts, implicatures}; предыдущий handoff инлайнится
в промпт следующего слоя (≤1500 симв.).

Интеграция: `translate(..., linguistic_layers=None|["all"]|[слои])` —
default off (backward compat Ф1–2.3); результат в `result["linguistics"]`;
demo `--layers=all|lexical,syntactic,...`.
Бюджет (стоп-точка №1): 4 вызова на цепочку; худший атом ≈ 8 LLM-вызовов
(extract+3 verify+4 слоя); на mock 200ms ≈1.6s, реально ≈14–16s < 30s;
гибрид (в: объединить слои попарно) — backlog после реальных замеров.

## Multi-focus Analysis (шаг 2.5)
Пакет `aeon/focus/`: `base.py` (ABC `FocusRole`, `Insight`, `FocusAnalysis`,
`FocusContext`), `prompts.py`, роли (`historian`/`philosopher`/`linguist`/
`esoteric`), `orchestrator.py` (`MultiFocusOrchestrator`), `aggregator.py`
(`MultiFocusResult`, `all_disagree`).

Роли НЕЗАВИСИМЫ (стоп-точка №3): `FocusContext` не содержит результатов
других ролей — «заражение» исключено структурно; общий вход — только
Atom (+ pack + linguistic layers). >1 роли — параллельно
(ThreadPoolExecutor; вызовы I/O-bound), 1 роль — sequential.
Alias `"all"` = historian+philosopher+linguist; `esoteric` — ТОЛЬКО явно.

**Why esoteric is opt-in (стоп-точка №1):** эзотерический фокус — самый
рискованный (нумерология/скрытые коды/конспирология легко имитируют
«анализ»). Промпт содержит жёсткие guardrails: только исторически
засвидетельствованные символические системы; запрещены numerology/hidden
codes/conspiracy; спекуляции — confidence ≤0.4; пустой список insights —
валидный ответ. Демо esoteric по умолчанию не показывает.

Агрегатор НЕ арбитрирует противоречия (фича: разные углы видят разное);
`all_disagree` — эвристика: две роли об одном предмете (Jaccard ≥0.5
значимых слов), но формулировки разные; семантический арбитраж (LLM) —
backlog. Зеркало детектора противоречий слоёв (3 строки, БЕЗ LLM: индекс
`(span, kind)` → сравнение value.casefold() — `linguistics/orchestrator.py`).

Интеграция: `translate(..., focus=None|["all"]|[роли])` — default off
(backward compat), результат в `result["focus"]`; demo `--focus=...`.
Неизвестная роль → `ConfigError` с понятным сообщением.

Бюджет (стоп-точка №4): 4 роли ≈ +8s последовательно / ≈2s параллельно;
worst atom (extract+3 verify+4 layers+4 focus) ≈ 12 вызовов ≈ 30–40s реально —
варианты (а) отключение layers при focus=all, (б) параллелить всё —
backlog 2.7 [не оптимизируем до реальных замеров].

Прочее (подозрения 2.4): handoff >1500 симв. → truncate + событие
`handoff_truncated` (тест есть); demo/test mock-значения (0.80–0.82,
insights) — **illustrative, не калиброванные** (реальный LLM даст разброс).

## Offline Knowledge Adapters (шаг 2.6)
Пакет `aeon/offline/`: `base.py` (ABC `OfflineAdapter`, `OfflineRecord`,
`OfflineProvenance`, `SqliteOfflineStore`), `pleiades.py`, `trismegistos.py`
(stub), `registry.py` (`get_adapter`/`register`/`list_adapters`).

Формат дампа — **JSONL**: строка 1 `{"meta": {...}}`, далее запись на строку
(стриминг без внешних парсеров); спецификация и инструкция атрибуции —
`data/<source>/README.md` (README в репо, сами данные — под .gitignore).

Механика (дополнения A–E): **атомарность** (transaction + периодические
commit + rollback — битая запись не оставляет частично загруженный дамп);
**индексы создаются ПОСЛЕ загрузки**; **идемпотентность** по `dump_version`
(same → skip, new → replace + событие `offline_dump_upgraded`);
**provenance** обязателен с `license` + `license_file_sha256` из бандла
(без sha256 → `OfflineDumpError`); **staleness**: дамп старше
`AEON_OFFLINE_MAX_AGE_DAYS` (90) → событие `offline_dump_stale`.

Цепочка в `PleiadesClient.get_place` (шаг 2.6): offline adapter (если
загружен) → live (при `AEON_OFFLINE_ALLOW_LIVE_FALLBACK=1`); офлайн-результат
помечается `source="offline_pleiades"`. **Детерминизм:** при offline-hit
live-кэш проверяется на расхождение (0 сети); несовпадение title →
событие `offline_live_conflict` — конфликт НЕ разрешается, offline
детерминирован и побеждает. Trismegistos — stub
(`no_public_dataset`: публичного датасета нет) — в pipeline не включается.

Метрики: `offline_cache_hit_rate`, `offline_dump_age_days`.
Demo: `python -m aeon.demo --text examples/greek/homer_iliad_1_1-10.txt --offline-pleiades tests/fixtures/dumps/pleiades_sample.jsonl`.

## Phase 3 roadmap (kickoff)
Порядок: **3.1 `.aeon v2` → 3.5 variant readings → 3.3 gold-standard**;
3.2 morphology — только после 3.3 И 2.7; 3.6 web — после 2.7;
3.4/3.7/3.8 — backlog. Дизайн и preflight — `docs/phase3_design.md`;
схема v2 — `schemas/aeon_v2.json` (required: thresholds_snapshot + mock;
forward-slots: variant_readings/morphology/cross_references = null).
Правила 2.7 (real API): ключ до 3.1 → пауза Ф3 и делаем 2.7; во время
шага → `key_available/defer_2_7` в state, продолжаем; после 3.3 → 2.7
приоритетно. Без real-API **не стартовать 3.2**.
Не в скоупе: раздувание паков до gold-standard; «AI-агент-исследователь».

## .aeon v2 format (шаг 3.1)
Пакет `aeon/format/` (writer/reader/validator/versioning); схема —
`schemas/aeon_v2.json`; спецификация — `docs/phase3_design.md`.
Контракт: required `thresholds_snapshot` + `mock` + `pipeline`
(steps_requested/executed/halted/failed — различает «не просили» vs
«остановлено»); `atom.content_hash` (вход) + `atom.atom_hash` (результат;
`meaning_hash` — legacy v1-поле); `extensions` — только namespaced-ключи,
core-override запрещён, `legacy_*` immutable (`AeonSchemaError`); semver
`X.Y.Z` (major>reader → «reader too old», major< → миграционный путь,
minor совместим).
**D3:** snapshot порогов фиксируется НА МОМЕНТ создания атома (translator),
writer читает его из атома и НЕ пересчитывает; атом без snapshot →
`AeonSchemaError`. **Mock-guard (стоп №2):** `mock=false` без
`DEEPSEEK_API_KEY` запрещён; обход только `force_unsafe=True` +
обязательный `force_reason` + аудит-лог `aeon_mock_flag_bypassed`
(reason/operator/trace_id).
**Миграция v1:** `load_v1_and_migrate` (production v1-reader;
`meaning_hash` — только в `extensions.legacy_v1_original`; хэши
пересчитываются — не угадываем семантику v1; v1-entities получают
v2-дефолты). Frozen fixture `tests/fixtures/aeon_v1/legacy.aeon`
(не пересоздаётся; паритет-тест — warning).
Demo: `--save-aeon PATH` / `--load-aeon PATH`. Сохраняются только
структурированные результаты (raw LLM — backlog `--save-raw`).

## Variant Readings (шаг 3.5)
Пакет `aeon/variants/` (`apparatus`/`prompts`/`selector`/`engine`) + sidecar-схема
`schemas/apparatus_v1.json` + пример `examples/apparatus/sappho_fr31.json`.
Философия: LLM только ВЫБИРАЕТ между внешне засвидетельствованными readings
(генерация запрещена); attribution обязателен — reading без editions или с
изданием вне `apparatus.editions` → `ApparatusError` (stdlib-валидатор, semver).

Селектор (`ReadingSelector`) — порядок решений (экономия LLM):
unanimous (тексты идентичны) → 0 вызовов, `editions_support` = union;
пустой context → `no_selection_possible` (reason «пустой контекст»);
Detective pre-filter (**mode `reading`**, context-agreement; шаблон = hypothesis):
`contradicted` → vetoed (`editions_vetoed: {reading: [editions]}`); 0 осталось →
all_vetoed; 1 осталось → `unanimous_after_veto` (0 вызовов; support — издания
выбранного); иначе LLM: readings нумеруются БЕЗ editions, rule 3 измеримо
(fewer editorial marks, тай-брейк `chosen_index: -1`), temp 0.0; conf < порога →
`no_selection_possible`. Порог `AEON_VARIANTS_MIN_CONFIDENCE` (default **0.5**):
выбор среди засвидетельствованного (риск ниже создания 0.75) и уже отфильтрован
Детективом.

**Work-guard:** ВСЕ значимые токены (≥4 симв., casefold; `_` — разделитель)
`apparatus.work` должны присутствовать в expected_work (`variant_work`, в demo —
`--variant-work` иначе stem текстового файла); mismatch → `ConfigError`
(не warn — молча неверный аппарат опаснее падения).

Порядок фиксирован: reconstruct (1.6) → variant (1.9) — восстановление lacunae
делает контекст полнее. API: `translate(..., variant_readings=PATH,
variant_work=...)` → `result["variant_readings"]`; demo
`--variant-readings PATH`; `.aeon v2`: `traces.variant_readings` + pipeline steps
(`variant_readings` в steps_requested/executed). Тесты: 29 (`tests/test_variants.py`).
Demo-значение `conf=0.71` у selected — **canned** (`DEMO_RESPONSES`), illustrative,
не вычисляется пайплайном; при неоднозначном stem (напр. `greek_text_1.txt`)
work-guard даст `ConfigError` — by design, передавайте `--variant-work` явно.

## Gold-standard corpus (шаг 3.3)
`gold/` (README, `annotation_schema.json` — schema_version +
marker_offsets_relative_to + optional entity role; `annotators.json`
`human:<handle>`; `texts/` — чистые тексты; `annotations/` — 28 записей/6 текстов;
`fixtures/mock_responses.json` — canned, ≠ gold; `metrics.md`) + пакет
`aeon/gold/` (loader: схема + integrity «segment_text ⊆ текст, offsets
валидны, сегменты не перекрываются»; metrics: P/R/F1 markers per kind,
entities (QID-exact | casefold), is_fragment acc, MAE, verdicts — stdlib, без
pandas/HF; runner; report CLI).

**Анти-циркулярность:** gold — ручная разметка (аннотатор `human:curator`,
draft до подписи); gold_mock использует canned-фикстуру, сознательно не равную
gold (тест `test_runner_mock_not_circular`). Q-ID только верифицированные
(live Wikidata API): Achilles=Q41746, Athenians=Q120096553, Zeus=Q34201 и др.;
неверифицированные → null. **Принцип: Q-ID never from memory** — даже
candidate-списки верифицируются (2026-10-14: 5/5 кандидатов оказались
неверны; Troy=Q22647, Juno=Q125046, Olympia=Q38888, Ajax=Q172725,
Palatium=Q200642 найдены через search).

**Mock-базлайн (факт):** markers macro F1 1.00 (lacuna 1.00 / supplement 1.00),
is_fragment acc 1.00; entities F1 0.06, completeness MAE 0.40, detective 0.00 —
canned-сигналы (стоп №3: два уровня тестов — `*_reports_value` всегда,
`*_meets_baseline` с xfail до real/2.7). Реальные цели — в `gold/metrics.md`.

pytest-маркеры: `gold_mock` (входит в дефолтный прогон), `gold_real`
(исключён в pytest.ini; skip без ключа; smoke — Plato). CLI:
`python -m aeon.gold.report --dataset gold/annotations/ --mode mock`.

**Аудит RU-флага (закрыт):** `examples/greek/plato_apologia_17a.txt` был
RU-конспектом → заменён подлинной grc-транскрипцией 17a; оба RU-файла в
`examples/greek/legacy/`; regression `tests/test_examples_corpus.py` (файлы
вне legacy/ обязаны содержать греческие codepoints; 2.1-тесты флаг не затронул —
они на inline-греческом).

## Phase 2 closure: results (2.7.3–2.7.6)
- **Real baseline (t3, 2026-10-14):** entities F1 **0.82** (fold-метрика;
  P 0.70 / R 1.00), detective **0.75**, expert/logician **1.00/1.00**,
  completeness MAE **0.09**, markers 1.00; **$0.0189** / 135 s (52 вызова,
  flash off-peak, thinking off). Raw: `gold/real_runs/2026-10-14_t3/`;
  дискавери — `gold/metrics.md`, распределение confidence —
  `gold/confidence_analysis.md` (2.7.5 — данные собраны, решение defer).
- **Contract-first refactor (worked example):** extractor v1 (semantic claims,
  taxonomy person|deity|group|place|object|abstract, language enforcement) +
  detective v1 (defensive-skip, quote-in-source NFC ≥3, grounded-ratio 0.7) +
  `build_claims` (meta-glue удалён) + v2-метаданные (`extractor_contract`) →
  гипотеза подтверждена измерением на ТЕХ ЖЕ gold: 0.24→0.82 и 0.00→0.75.
- **DeepSeek V4:** flash — thinking по умолчанию (см. Known Quirks);
  тарифы/peak-часы/cache-hit в конфиге; диагностический кейс t2 (28 пустых
  ответов) сохранён как документ API-quirk.
- **Design principle (урок):** focus-роли НЕ потребляют chain (вход:
  source_text + entities + linguistic summary) — правильная развязка
  зависимостей защитила от coupling-каскада: grammar-heavy chain (57%)
  не сломал focus → Rule-3 v1 green.
- **Design principle (3.2):** для каждой морфологической категории в
  enum'ах промпта — минимум один few-shot пример; LLM не экстраполирует
  правило на новый класс без примера (3 накопленных случая: adj/adjective,
  participle, imperative). Голая категория в enum'е = слот для догадки.
- **Design principle (3.2, #1):** `finish_reason` проверяется во ВСЕХ
  LLM-вызовах (провайдер): `length` → событие `llm_output_truncated` +
  один retry ×2 бюджет; `max_tokens` масштабируется по input
  (morph: `max(2000, min(8000, форм×250))`); три случая truncation
  (2.7.3-flash-thinking, morph_t2) → инфраструктурная защита (5e4125d).
- **Design principle (3.2, #3):** gold — не догма; эволюция только через
  source-verified патчи (Class A 1.1.1: morph_v1 нашёл 5 gold-дефектов —
  cicero nom ×4, homer ἣ; патч по source-diff «было/стало/почему»,
  без подгонки под model).
- **Design principle (3.2, #4):** F1 — метрика согласованности с gold, не
  «качество»: рост F1 может быть bad (gold упрощён под model), падение —
  good (gold стал правильнее). Всегда gold-diff рядом с F1-diff; отчёт без
  gold-diff — не отчёт. Worked example #2: person 0.97→0.90 после 1.1.1 —
  впервые измерен реальный gap вместо совпадения неправильностей.
- **Design principle (#5, maintenance 2026-10-14):** behavioral rule в AGENTS
  обязана иметь CI/unit-guard, иначе нарушается (было 4 truncation-бага при
  правиле «finish_reason проверяется»). Guards: `tests/test_llm_guards.py`
  (единый SDK-провайдер — прямой `chat.completions` вне `aeon/llm/` запрещён;
  `except: pass` запрещено; бюджет-дефолт клиента = 4000).
- **Design principle (#6, maintenance 2026-10-14):** behavioral scans — **AST,
  не regex/string**: линейный скан `except: pass` дал 0, AST-скан — 12
  (многострочный формат). Инструмент проверки обязан быть корректнее
  проверяемого.
- **Design principle (#7, 3.4 scoping 2026-10-14):** architectural choice —
  только после **эмпирического теста**, не интуиции: лемма-префильтр для
  cross-refs отклонён на основе прогона (мусор через артикли + структурно
  слеп для cross-language), а не «кажется сложным» — сэкономил 2 дня
  неработающего filtered-подхода.
- **Design principle (#8, 3.4 scoping 2026-10-14):** coverage gaps —
  **explicit**: prompt-only фичи (без gold-примеров) обязаны быть в разделе
  `coverage_gaps` соответствующего документа, не в inline-комментарии.
  Пример: `direct_citation` ×0 в gold (prompt-only, F1 = N/A) —
  задокументирован в `docs/phase3_34_design.md` §10.
- **Design principle (#10, 3.4.1 2026-10-14):** **validators before write** —
  для любой схемы данных валидатор запускается ДО записи артефакта
  (gold: `validate_cross_ref_schema` fail-fast + invariant #9 при load;
  `.aeon v2`: validator; apparatus: attribution). Схема без enforced-валидатора
  на записи — suggestion, не контракт.
- **Design principle (#9, 3.4 countersign 2026-10-14): ACTIVE** (подтверждён
  трижды: `direction`, `matched_lemmas` вне segment, «формула И/ИЛИ»). При
  countersign — **прогонять schema-инварианты на samples ПРОГРАММНО**, не
  полагаться на глаз; инварианты → loader-валидация (`validate_cross_ref_schema`)
  + тесты. Корень трёх находок — итеративное расширение схемы (каждое новое
  поле без precedent) — норма для pilot; фикс — машино-проверка при записи.
- **Бюджет-политика LLM (аудит 2026-10-14):** 15 call-sites — все через
  `DeepSeekClient._call(+_call_json)` → единый провайдер (finish_reason-retry —
  safety-net там); default max_tokens = 4000; sites с большими/масштабными
  выводами задают явно (morph: форм×250; linguistics: 6000). Legacy v3.0-фасад
  `deepseek.py` (extract_meaning/translate_text/generate_code/semantic_compare/
  describe_for_image) — uncovered (76%), кандидат на deprecation-аудит.
  Proposal Ф4 (Google-AI-консультация): `call_structured(prompt, schema,
  budget_hint)` c dynamic budget (ctx − prompt − buffer) + has_more/next_cursor
  chunking для unbounded arrays (кейс: linguistics 124 findings).
- **Morphology baseline (3.2, morph_v1, gold 1.1.1):** F1 all: pos 0.98 /
  lemma 0.92 / tense 0.96 / mood 0.98 / voice 0.93 / person 0.90 /
  case 0.99 / number 0.99 / gender 0.98 (28 атомов, 224 формы, $0.0214;
  raw `gold/real_runs/2026-10-14_morph_t4/`; детали — `gold/metrics.md`).
- **Known gaps:** Pleiades README links (network); Trismegistos datasets (нет
  публичного API); `deepseek-chat` — deprecated alias-fallback; zero-gold F1
  артефакт (papyrus/sappho: 1+1 borderline FP); role-consistency 10.7%
  (accepted для v1); grammar-heavy chain (accepted, trigger-revisit: новый
  chain-потребитель или gold + grammar-sensitive text); mock-fixtures alignment
  (backlog); anchor_language inference из pack для старых v2 (backlog);
  порог 0.85 (Фаза 4 calibration).
- **Backlog Ф3+:** **3.2 morphology — рекомендуемый первый** (разблокирован);
  3.9 embeddings-provider; 3.4 cross-references; 3.6 Web UI/API; contract v1.2
  (Rule 3 content-first; Rule 5 emphasis + post-hoc repair; edge-cases:
  **generic office/deity rejected** — named referent требует specific
  identity, не class membership; revisited если gold добавит такие кейсы);
  deepseek-chat compatibility audit (при деprecation).

## Tech Stack
- Python 3.11 (Windows dev), приоритет stdlib
- LLM: DeepSeek (OpenAI-совместимый), фасад `aeon.llm.DeepSeekClient`
- Embeddings: sentence-transformers (MiniLM 384D default, LaBSE опц.) — pluggable
- Web: FastAPI + SPA; CLI: REPL (`aeon/cli.py`)
- Формат: `.aeon` бинарный (чтение v1 сохраняется)

## Conventions
- Русские docstrings и комментарии (стиль проекта)
- Новые модули покрываются pytest-тестами; сеть по умолчанию отключена
  (маркеры `network`, `models` — исключены из дефолтного прогона)
- Структурное логирование: `aeon/logging_config.py` → `log_event` (JSON-lines)
- Метрики: `aeon/metrics.py` → `METRICS` (stdlib, без внешних зависимостей)
- Test/dev-зависимости — только в `requirements-dev.txt`
- MockLLM — в `aeon/testing.py` (общий с demo; `latency_ms` имитирует сеть)

## Commands
- Тесты: `python -m pytest -q` (live: `pytest -m network -k pleiades`)
- Coverage (обходной раннер — см. quirks): `python tools/run_coverage.py`
- Demo верификации: `python -m aeon.demo --text examples/latin/caesar_bg_1_1.txt --verify=full --language=la`
  (mock 200ms/вызов; `--real` — с DEEPSEEK_API_KEY; `--verify=off|basic|full`;
  `--language` — ISO-код пака: нормализация + маркеры;
  `--reconstruct` — Fragment Hypothesis Engine: гипотезы / no_reconstruction;
  `--layers=all|lexical,syntactic,...` — Chain-of-Linguistics;
  `--focus=all|historian,philosopher,...` — Multi-focus (all без esoteric);
  `--variant-readings PATH` (+`--variant-work`) — Variant Readings (шаг 3.5):
  выбор среди attested readings, пример `examples/apparatus/sappho_fr31.json`)
- Gold-standard: `python -m aeon.gold.report --dataset gold/annotations/ --mode mock`
  (real — при ключе; `pytest -m gold_mock` / `-m gold_real`)
- verify_mode в API: `translator.translate(..., verify_mode="off|basic|full", language_pack=None)`
  (legacy `verify=True` ≡ `verify_mode="full"`)
- Реестр паков: `python -c "from aeon.language import registry; print(registry.list_available())"`
  → `['grc', 'la']`

## Key Decisions
- **Config access (канонический):** `CONFIG.verification.detective` — иерархический;
  плоский `CONFIG.detective` — convenience-алиас (новый код — только иерархический).
- **Дефолты конфига = поведение v3.0 1:1** (`aeon/config.py`;
  `legacy_config_used_by`: legacy-проекция risk-полос + review-threshold агрегатора).
- **LLM-слой:** пакет `aeon/llm/`; `from aeon.llm_client import DeepSeekClient` — shim.
- **Ретраи:** backoff + `Retry-After` (max); retryable = 5xx/408/429/timeout/connection.
  `llm_call.latency_ms` = все попытки (включая backoff-паузы), поля attempts/retries.
- **JSON-repair:** только stdlib (fences, скобки, trailing commas, ast). При неудаче
  канал v3.0: `{"raw_response", "parse_error"}` + лог; extractor → rule-fallback.
- **Entity Linking:** opt-in (`AEON_ENTITY_LINKING=1`; contact_email обязателен при
  включении — fail-fast). Wikidata Action API, UA с контактом, rate limit ≤1 rps,
  SQLite-кэш 7д, offline-режим; веса скоринга — `AEON_SCORE_WEIGHT_*`.
- **Fragment-понятия ортогональны:** `is_fragment` — свойство ИСТОЧНИКА (лакуна);
  `completeness_score` — качество ИЗВЛЕЧЕНИЯ (5 полей); агрегат `needs_attention`.
- **Verification 2.0 (точная формула CVI — для воспроизводимости):** negatives
  доминируют → `contradicted` (conf = max по негативным); нет positives →
  `abstained` (conf 0.0); **«один верификатор не сертифицирует» (fix 2.7.2):**
  `len(positives) < 2` при ≥1 нейтрале → `abstained` (reason
  `insufficient_positives`; CVI сохраняется для диагностики; действует и в
  2-агентном basic-режиме); **CVI = среднее confidence ПОЛОЖИТЕЛЬНЫХ вердиктов**
  (round 4; нейтральные/abstained в среднее НЕ входят); CVI < 0.50
  (`abstention_threshold`) → `abstained`; needs_review при CVI < 0.85
  (=1−`legacy.risk_verified_max`) и только у `verified` (при
  `insufficient_positives` — False: система уверена, что данных мало; review
  зарезервирован за вердиктом с оговорками). В `combined` есть `reason`
  (`negative_dominates`/`no_positives`/`insufficient_positives`/`below_threshold`/""). Пример: mean(0.91, 0.90) = 0.905 →
  в выводе `{cvi:.2f}` отображается «0.91». Per-agent abstention (detective
  conf<0.85, logician coherence<0.60); logician при <2 claims — abstained.
- **verify_atom:** legacy-ключи (consistency/grounding/hallucination_risk/
  overall_verdict) + v4.0 (agents/combined/cvi/abstained/reasoning_trace).
- **LanguagePack (Ф2):** вариант A (промпты + словари + special tokens;
  морфология — Ф3); stdlib-only (`unicodedata`); detect() — декларативные
  `unicode_ranges` + опциональный `detect_heuristic`; registry —
  eager-регистрация + lazy-инстанциация.
- **Нормализация пака — только pipeline:** оригинал сохраняется в
  `result["source"]["content"]` (refinement 2.0 №2).

## Known Quirks & Limitations
- **Wikidata:** ошибки API = HTTP 200 + `{"error": {...}}` (не HTTP-код!). Каждый
  новый клиент обязан различать HTTP-ошибки и API-error-payload.
- **Trismegistos:** публичного API нет (SSL-цепочка + 403 анти-бот) → stub
  (`no_public_api`); датасеты — Фаза 2.
- **Pleiades:** недоступен из dev-сети (TCP ok, нет ответа) → защитный парсер +
  live-тест `pytest -m network -k pleiades`; offline dump adapter — Фаза 2.
  Клиент ходит только по hostname.
- **Детектив ↔ переводы:** exact-quote работает лишь с исходным языком; для
  переводов — `unverifiable_due_to_missing_data` (нейтрально). `allow_translation_match` — Ф2.
- **Expert:** различие `no_external_data` vs `external_data_silent` пока отсутствует (Ф2).
- **Coverage на Windows:** pytest-cov (`--cov`) падает access violation (0xC0000005)
  при загрузке torch DLL. Обход: `python tools/run_coverage.py` (Coverage API
  стартует до pytest). Не возвращаться к `pytest --cov`.
- **Coverage-раннер — кросс-платформенный:** `tools/run_coverage.py` использует
  только Coverage API, валиден и на Linux (там штатный `pytest --cov` тоже
  работает); версия закреплена `coverage>=7.4,<8.0` в requirements-dev.
- **Network-тесты в CI (план):** `pytest -m network` — отдельная НЕблокирующая
  джоба; локально — по требованию; Pleiades live-тест skip при недоступности.
- **Real-API gap:** demo-метрики на mock (200 ms/вызов — экстраполяция); реальный
  DeepSeek ≈1.5–4 s/вызов → 4 вызова ≈6–16 s; Ф2 multi-focus (до 12 вызовов)
  может потребовать параллелизации (backlog шаг 2.7).
- **DeepSeek V4 quirks (актуально 2.7.3, 2026-10):** `deepseek-flash` —
  **thinking-модель по умолчанию**: reasoning-токены входят в `max_tokens` →
  `finish_reason=length` при пустом `content` (сигнатура: `reasoning_tokens>0` +
  empty content). Non-reasoning задачи: `thinking: {"type": "disabled"}` —
  реализовано в `DeepSeekClient` (`LLMConfig.disable_thinking`, env
  `AEON_LLM_DISABLE_THINKING`; auto `extra_body` для flash). Легаси-алиас
  `deepseek-chat` = non-thinking (обслуживается V4.1-Flash). `/models` →
  `[deepseek-flash, deepseek-v4-pro]`; цены off-peak 0.15/0.60, cache-hit
  0.003, peak ×2 (01–04/06–10 UTC Пн–Пт = 04–07/09–13 MSK); контекст до 1M.
  Кейс провала t2 (28 пустых ответов) сохранён: `gold/real_runs/2026-10-14_t2/`.
