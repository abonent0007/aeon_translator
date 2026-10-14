# Контракт: extractor v1 — НОВОЕ ТЗ (не ревизия v3.0-промпта)

**Статус:** FINAL DRAFT (2.7.3, контрактный аудит) — до апрува куратора не кодится.
**Область:** `aeon/extractor.py::_extract_structure_llm`.

> **Это новое ТЗ, а не документирование существующего.** Текущий промпт —
> v3.0-эры: он писался для задачи **семантического перевода**
> (`domain` = business/technology; `entity` = concept/property/abstract;
> `explanation_chain` = «HOW you arrived»). Он не пересматривался с Ф0 и не
> подходит для задачи **NER + verifiable claims на древних текстах**.
> Finding: `extractor_prompt_v3_legacy` (HIGH).

## Принципы (новые)
1. **Meta ⊥ семантика.** intent/domain — отдельные поля; НЕ дублируются внутри
   entities/evidence/explanation_chain.
2. **Язык источника обязателен** для entities.name, evidence, explanation_chain
   (см. § Language enforcement).
3. **Пустое лучше выдуманного:** `[]`/`""` — валидны; не заполнять «для полноты».
4. **Claims = verifiable assertions** — утверждения о СОДЕРЖАНИИ, проверяемые
   против текста; не инструкции разбора, не мета-информация.

## Поля (контракт v1)
- **intent** — ровно одно: `[question, request, emotion, statement, command, declaration]`.
- **domain** — ровно одно: `[science, technology, emotion, philosophy, general,
  art, business, politics, literature, history, epigraphy, papyrology, religion]`
  (расширено под древние тексты: литература/история/эпиграфика/папирология/религия);
  **domain — primary register, не exhaustive categorization**: эпиграфический
  исторический документ может получить `epigraphy` ИЛИ `history` — допустимо
  любое, фиксируется первичный регистр текста.
- **entities** — ТОЛЬКО именованные референты:
  - INCLUDE: личные имена (Σωκράτης), топонимы (Gallia), этнонимы/группы
    (Ἀθηναῖοι, Belgae), божества (Ζεύς, Μοῦσα), водные объекты (Garumna);
  - EXCLUDE: местоимения, нарицательные/абстракции, глаголы/действия, описания
    («мои обвинители»), переводы, приложения внутри именной фразы;
  - `name` — минимальная именная форма как в тексте (без артикля: `Ἀθηναίων`,
    не `ὁ Ἀθηναίων`; без патронимики: `Ἀχιλῆος`, не `Πηληϊάδεω Ἀχιλῆος`);
  - **`type` ∈ `person | deity | group | place | object | abstract`** (v1.1,
    решено на pre-commit-2): `deity` — божества (Мοῦσα ≠ person);
    `group` — коллективы/племена (Helvētiōs ≠ person); `place` — топонимы;
    `abstract` — концепты/события (глаголы и прилагательные — НИКОГДА не entities);
  - `role` ∈ agent|patient|instrument|location|time|manner|goal — **описывает
    синтаксическую функцию в клаузе, а не онтологический класс**; может
    ссылаться и на не-entities (Q3: `semantic_roles` тоже могут ссылаться на
    common nouns/pronouns — они описывают структуру клаузы, не инвентарь
    референтов; тест `test_semantic_role_references_non_entity_allowed`);
  - `span` — точная подстрока; нет сущностей → `[]`.
- **semantic_roles / semantic_primitives** — без изменений (semantic_roles может
  ссылаться на не-entities, Q3); **Note B:** `entities[].role` и `semantic_roles`
  инверсны — держим ОБА (вариант (a), обратная совместимость), но добавляем
  валидацию консистентности (`test_semantic_roles_entity_consistency`, коммит 3:
  если `entities[i].role=X`, то `semantic_roles[X]` содержит `entities[i].name`
  или его span).
- **evidence** — **1–4 НЕ-избыточные** точные цитаты (verbatim-подстрока, язык
  источника); **одна цитата не должна быть подстрокой другой** — покрытие якорей
  достигается достаточной длиной, а не дублированием; для короткого сегмента
  **одна полная цитата валидна**.
- **explanation_chain** — **1–5 семантических утверждений** о содержании, каждое
  с verbatim-цитатным якорем; ЗАПРЕЩЕНЫ инструкции («Identify…», «Recognize…»,
  «Note…», «Parse…», «Determine…», «Step N:»), meta («Intent: …», «Domain: …»),
  перевод. Few-shot: 2–3 примера на источниковом языке (добавляются в коммите 2).
- **confidence_breakdown / complexity / urgency / extraction_confidence /
  semantic_tokens** — без изменений; semantic_tokens допускают English-концепты.

## Статус полей v3.0 в contract v1 (Issue 3)

| Поле v3.0 | Статус v1 | Обоснование |
|---|---|---|
| `intent` | ✅ сохранено | извлекать |
| `domain` | ✅ сохранено | словарь расширен (древние тексты) |
| `entities` | ✅ переопределено | Q1: person\|deity\|group\|place\|object\|abstract |
| `semantic_roles` | ✅ сохранено, уточнено | Q3: может ссылаться на не-entities; Note B |
| `evidence` | ✅ переопределено | 1–4, не-избыточные (Issue 1) |
| `explanation_chain` | ✅ переосмыслено | semantic claims (EN + verbatim anchor) |
| `semantic_primitives` | ✅ сохранено как v3.0 | потребителей не выявлено — кандидат на deprecation в contract v2 |
| `semantic_tokens` | ✅ сохранено как v3.0 | English-концепты допустимы |
| `complexity` / `urgency` | ✅ сохранено как v3.0 | в SemanticAtom, downstream не критичен |
| `confidence_breakdown` | ✅ сохранено как v3.0 | legacy-проекция |
| `extraction_confidence` | ✅ сохранено **критично** | используется всеми потребителями (atom) |

**Итог:** v1 **не расширяет scope** — все поля сохраняются; пересмотр их судьбы
(deprecation) — отдельный contract-аудит (шаг «contract: audit LLM step outputs»).
Промпт запрашивает все поля как раньше (кроме переопределённых выше).

## Anti-patterns from 2.7.3 (что реально вернула модель → правило)

| Ответ LLM (2.7.3) | Почему неверно | Контрактное правило |
|---|---|---|
| `ὑμεῖς` (type=person) | местоимение, не именованный референт | исключить местоимения (все лица/числа) |
| `πεπόνθατε` (type=action) | глагол-сказуемое, не референт | исключить глаголы/действия из entities |
| `sitting, near, sweet` | **перевод** на английский, не язык источника | language enforcement: переводы запрещены |
| `Πηληϊάδεω Ἀχιλῆος` | патронимическая фраза вместо имени | минимальная именная форма: `Ἀχιλῆος` |
| `μῆνιν` (type=abstract) | нарицательное «гнев», не референт | исключить common nouns/абстракции |

## Language enforcement (v1.1, с условиями куратора)
- `entities[].name`, `evidence[]` — **строго язык источника** (перевод запрещён);
  при неуверенности в греческой/латинской форме — `name: null`, **не** перевод.
- `explanation_chain[]` — **working analytical prose in English** (рабочий язык
  пайплайна). **It is NOT a translation and must NOT be cited as such.**
  (Condition 1 — обязательная формулировка.) Each claim MUST contain a
  **verbatim anchor** from the source (Greek/Latin); the anchor is the sole
  evidence-bearing element.
- **Condition 2 — anchor обязателен:** claim без verbatim-якоря → отбрасывается
  defensive-skip'ом (коммит 3) + событие `claim_no_anchor` (medium);
  тест `test_claim_without_anchor_skipped`. Дополнительно (Q2, правило (b)):
  **каждый verbatim-якорь claim'а должен быть подстрокой хотя бы одной
  evidence-цитаты** — evidence остаётся пулом для верификации.
- **Condition 3 — метаданные в `.aeon v2`:** в `atom` добавляются
  `chain_language: "en"` и `anchor_language: <pack.iso_code>` (grc/la) —
  потребитель v2 обязан знать, что chain = рабочий анализ, не цитата;
  тест `test_v2_records_chain_language`; реализация — мини-коммит 2b
  (SemanticAtom + writer/validator).
  **Note A:** `anchor_language` — **primary** язык сегмента (не exhaustively):
  при смешанных вставках (греческий с латинскими вставками в эпиграфике)
  указывается основной; якоря могут быть на разных языках.
- Тексты с диакритикой: сохранять диакритику как в источнике (NFC-форма).

## Известные ограничения (для пользователя)
- **Literary significance ≠ entity status.** `μῆνιν` («гнев») в Il. 1.1 —
  тематическое ядро поэмы, но NER-контракт исключает его как common noun
  (gold-аннотация Homer его также не включает — согласовано). Значимые
  НЕ-сущности обрабатываются слоями лингвистики (2.4), не через NER —
  система «не видит» гнев Ахилла как entity by design, но видит в lexical/
  semantic layers.

## Worked example: anchor⊆evidence поймал диакритику (2026-10-14)
При драфте Example C якорь `τῷ Διὶ` (grave — как в evidence) разошёлся с
`Διί` (acute) в chain: правило «anchor ⊆ evidence» выявило рассинхрон **до**
коммита промпта. Правило не декоративно — оно **исполняемо** и сработало на
собственном few-shot (этот случай — мета-доказательство необходимости
валидации якорей в коммите 3).

## Совместимость и реализация
- Коммит 2: `fix: extractor produces semantic claims only (contract v1)` —
  переписанный промпт + расширенный domain-словарь + language enforcement +
  few-shot (2 примера из Appendix). Затрагивает `aeon/extractor.py`.
- Коммит 2b: `feat: v2 chain_language/anchor_language metadata` —
  Condition 3 (SemanticAtom + `aeon/format` writer/validator + переводчик).
- English-leak (≈4/28 в 2.7.3: какие сегменты/корреляции) — **пересчитать после
  re-run**; если останется — отдельная проблема (не следствие контракта).

## Appendix: APPROVED few-shot (для промпта, коммит 2)
Оба примера — **вне gold-корпуса** (анти-утечка): Odyssey 1.1, BG 1.2.

**Example A (Greek):**
TEXT: "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ πλάγχθη"
```json
{"intent": "command", "domain": "literature",
 "entities": [{"name": "Μοῦσα", "type": "deity", "role": "agent", "span": "Μοῦσα"}],
 "semantic_roles": {"agent": "Μοῦσα", "patient": "ἄνδρα", "instrument": "",
                    "location": "", "time": "", "goal": "μοι", "manner": ""},
 "semantic_primitives": ["existence", "action", "relation", "purpose", "quantity"],
 "evidence": ["ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον", "ὃς μάλα πολλὰ πλάγχθη"],
 "explanation_chain": [
   "Narrator invokes the Muse to sing of a much-wandering man (ἔννεπε imperative).",
   "The Muse is the agent of the song; ἄνδρα is its subject, πολύτροπον his defining trait.",
   "The relative clause ὃς μάλα πολλὰ πλάγχθη defines the extent of his wandering."],
 "confidence_breakdown": {"intent": 0.95, "domain": 0.9, "entities": 0.9, "roles": 0.8},
 "complexity": 0.5, "urgency": 0.1, "extraction_confidence": 0.9,
 "semantic_tokens": ["invocation", "muse", "wandering", "hero"]}
```
(Показывает: `ἄνδρα`/`μοι`/`πολύτροπον` исключены; Муза = deity; все якоря
покрыты evidence.)

**Example B (Latin):**
TEXT: "Apud Helvētiōs longē nōbilissimus fuit et dītissimus Orgetorīx."
```json
{"intent": "statement", "domain": "history",
 "entities": [{"name": "Helvētiōs", "type": "group", "role": "location", "span": "Helvētiōs"},
              {"name": "Orgetorīx", "type": "person", "role": "agent", "span": "Orgetorīx"}],
 "evidence": ["Apud Helvētiōs longē nōbilissimus fuit et dītissimus Orgetorīx"],
 "explanation_chain": [
   "Orgetorix's superlative standing among the Helvetii is asserted through two coordinated superlatives (nōbilissimus, dītissimus, Orgetorīx).",
   "The superlatives mark his pre-eminence within that community (Helvētiōs)."],
 "...": "остальные поля аналогично Example A"}
```
(Evidence: **одна** полная цитата — сегмент короткий, дубликат запрещён (Issue 1).
Q4: `Helvētiōs` = group + role=location — theta-role в терминах контракта.)

**Example C (Greek, эпиграфический регистр; конструктивный пример — не аттестация):**
TEXT: "Ἀθηναῖοι ἀνέθεσαν τῷ Διὶ τρόπαιον ἐν Ὀλυμπίᾳ."
```json
{"intent": "statement", "domain": "epigraphy",
 "entities": [{"name": "Ἀθηναῖοι", "type": "group", "role": "agent", "span": "Ἀθηναῖοι"},
              {"name": "Διὶ", "type": "deity", "role": "goal", "span": "Διὶ"},
              {"name": "τρόπαιον", "type": "object", "role": "patient", "span": "τρόπαιον"},
              {"name": "Ὀλυμπίᾳ", "type": "place", "role": "location", "span": "Ὀλυμπίᾳ"}],
 "evidence": ["Ἀθηναῖοι ἀνέθεσαν τῷ Διὶ τρόπαιον ἐν Ὀλυμπίᾳ"],
 "explanation_chain": [
   "The inscription records a dedicatory act by the Athenians, addressed to Zeus and located at Olympia (ἀνέθεσαν, τῷ Διὶ, Ὀλυμπίᾳ).",
   "The dedication formula assigns the object (τρόπαιον) and the recipient deity (Διὶ)."],
 "...": "остальные поля аналогично Example A"}
```
(Покрывает `place` и `object` — Issue 2(c); тип `abstract` — редкий, показан в
правиле промпта «all six types equally valid», не в примере.)
