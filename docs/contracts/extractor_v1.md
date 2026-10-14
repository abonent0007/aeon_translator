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
  (расширено под древние тексты: литература/история/эпиграфика/папирология/религия).
- **entities** — ТОЛЬКО именованные референты:
  - INCLUDE: личные имена (Σωκράτης), топонимы (Gallia), этнонимы/группы
    (Ἀθηναῖοι, Belgae), божества (Ζεύς), водные объекты (Garumna);
  - EXCLUDE: местоимения, нарицательные/абстракции, глаголы/действия, описания
    («мои обвинители»), переводы, приложения внутри именной фразы;
  - `name` — минимальная именная форма как в тексте (без артикля: `Ἀθηναίων`,
    не `ὁ Ἀθηναίων`; без патронимики: `Ἀχιλῆος`, не `Πηληϊάδεω Ἀχιλῆος`);
  - `type` ∈ concept|person|object|action|property|abstract (сохраняется);
  - `role` ∈ agent|patient|instrument|location|time|manner|goal (сохраняется);
  - `span` — точная подстрока; нет сущностей → `[]`.
- **semantic_roles / semantic_primitives** — без изменений.
- **evidence** — 2–4 точные цитаты (verbatim-подстрока, язык источника).
- **explanation_chain** — **1–5 семантических утверждений** о содержании, каждое
  с verbatim-цитатным якорем; ЗАПРЕЩЕНЫ инструкции («Identify…», «Recognize…»,
  «Note…», «Parse…», «Determine…», «Step N:»), meta («Intent: …», «Domain: …»),
  перевод. Few-shot: 2–3 примера на источниковом языке (добавляются в коммите 2).
- **confidence_breakdown / complexity / urgency / extraction_confidence /
  semantic_tokens** — без изменений; semantic_tokens допускают English-концепты.

## Anti-patterns from 2.7.3 (что реально вернула модель → правило)

| Ответ LLM (2.7.3) | Почему неверно | Контрактное правило |
|---|---|---|
| `ὑμεῖς` (type=person) | местоимение, не именованный референт | исключить местоимения (все лица/числа) |
| `πεπόνθατε` (type=action) | глагол-сказуемое, не референт | исключить глаголы/действия из entities |
| `sitting, near, sweet` | **перевод** на английский, не язык источника | language enforcement: переводы запрещены |
| `Πηληϊάδεω Ἀχιλῆος` | патронимическая фраза вместо имени | минимальная именная форма: `Ἀχιλῆος` |
| `μῆνιν` (type=abstract) | нарицательное «гнев», не референт | исключить common nouns/абстракции |

## Language enforcement (отдельный раздел)
- Все `entities[].name`, `evidence[]`, `explanation_chain[]` — **в языке оригинала**.
- Перевод на английский (или любой другой) — **запрещён**; при неуверенности в
  греческой/латинской форме — `name: null` (место сущности сохранить), **не** перевод.
- Тексты с диакритикой: сохранять диакритику как в источнике (NFC-форма).

## Известные ограничения (для пользователя)
- **Literary significance ≠ entity status.** `μῆνιν` («гнев») в Il. 1.1 —
  тематическое ядро поэмы, но NER-контракт исключает его как common noun
  (gold-аннотация Homer его также не включает — согласовано). Значимые
  НЕ-сущности обрабатываются слоями лингвистики (2.4), не через NER —
  система «не видит» гнев Ахилла как entity by design, но видит в lexical/
  semantic layers.

## Совместимость и реализация
- Коммит 2: `fix: extractor produces semantic claims only (contract v1)` —
  переписанный промпт + расширенный domain-словарь + language enforcement +
  few-shot (2–3 примера). Затрагивает только `aeon/extractor.py`.
- English-leak (≈4/28 в 2.7.3: какие сегменты/корреляции) — **пересчитать после
  re-run**; если останется — отдельная проблема (не следствие контракта).
