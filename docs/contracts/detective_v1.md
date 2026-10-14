# Контракт: detective v1 (grounding claims)

**Статус:** FINAL DRAFT (2.7.3) — до апрува куратора не кодится.
**Область:** `aeon/verification/detective.py` + `verification/base.py`
(`build_claims`) + вызывающие (`translator.py`, `gold/runner.py`, `demo.py`).

> Связанный finding: `detective_quote_not_verified` (**CRITICAL**) —
> сейчас `quote` принимается по НЕПУСТОТЕ (`detective.py:119`), подстрочность
> source не проверяется → «детектив, который не верифицирует».

## Вход
- `source_text` — сегмент источника.
- `claims` — СПИСОК semantic-claims (см. extractor v1).

**Контракт вызывающего (fix):**
- **Убрать meta-glue** в `translator.py:173`, `gold/runner.py:121`, `demo.py:398`
  (`claims = explanation_chain + ["Intent: …", "Domain: …"]` — удалить хвост).
- Новый helper в `verification/base.py`:
  `build_claims(atom) -> list[str]` — возвращает **только**
  `atom.explanation_chain`, отфильтрованный от инструкционных/meta-строк;
  meta НЕ добавляет. Тесты: `test_build_claims_excludes_meta`,
  `test_build_claims_filters_instructions`.

## Defensive-skip (в детективе, вторая линия защиты)
Строки, матчащие любой из regex (case-sensitive, начало строки):
```
^(Intent|Domain|Type|Complexity|Urgency|Confidence):
^(Identify|Recognize|Determine|Note|Find|Locate)(\s|:)
^Step \d+:
```
- SKIP строки из оцениваемого набора; событие `claim_skipped_meta`
  (поля: row — исходная строка, reason) — для аудита.
- Пропущенные строки входят в `details.skipped` и НЕ влияют на ratio.
- Тест: `test_defensive_skip_bare_instruction_word` (edge: строка `"Identify"`
  без пробела/двоеточия — покрывается `(\s|:)`-альтернативой).

## Grounding (per-row) — fix
- строка grounded ⇔ `not contradicts` И `len(quote.strip()) >= 3` И
  `NFC(quote) in NFC(source_text)`.
- Если `quote` непустой, но **не подстрока**: событие
  `detective_quote_not_in_source` (level=high, поля: quote, claim) —
  защита от галлюцинации цитат; строка **не** считается grounded.
- Тесты: `test_detective_hallucinated_quote_rejected`,
  `test_detective_quote_nfc_matched`.

## Агрегация — fix (Q1)
- negatives → contradicted (доминируют, как есть).
- `n = len(semantic_rows_after_skip)`; `grounded_ratio = grounded / n`.
- **ratio == 1.0 и n >= 2** → grounded, `confidence = avg(conf)`.
- **ratio >= threshold** (иначе) → grounded, `confidence = ratio × avg(conf)`
  (пониженная уверенность при частичном покрытии).
- **ratio < threshold** → unverifiable (conf = ratio, как сейчас);
  `n == 0` → **neutral с reason `no_semantic_claims`** + событие
  `detective_no_semantic_claims` (medium): это НЕ «нет данных о тексте», а
  дефект extractor (все строки — meta/инструкции); после коммита 2 должно
  исчезнуть — если не исчезнет, сигнал что промпт всё ещё производит инструкции.
  Тест: `test_detective_no_semantic_claims_neutral_with_reason`;
  пустой claims → neutral (как есть).
- Конфиг: `CONFIG.verification.detective.grounded_ratio_threshold`,
  default **0.7** («⅔ + округление», задокументировано);
  env `AEON_DETECTIVE_GROUNDED_RATIO`.
- Тесты: `test_detective_grounded_ratio_2_of_3_grounded`,
  `test_detective_below_ratio_threshold_abstains`.

## Порог min_confidence 0.85 (Q3) — НЕ трогать
- Структурные фиксы (skip, quote-verify, ratio) — сначала; порог — после.
- Data-задача (перед любым решением): зафиксировать распределение confidence
  поверх raw 2.7.3 (52 вызова): avg/min/max/histogram по grounded-строкам;
  проверить кейсы ratio=1.0 с avg<0.85 (sappho seg3: 0.83).
- min-based агрегатор — обсуждать только на данных, отдельным решением.

## Выход
- `Verdict {verdict, confidence, reasoning, details.per_claim}` +
  `details.skipped` (новое); события `claim_skipped_meta`,
  `detective_quote_not_in_source`.
- Реализация: коммит 3 `fix: detective defensive-skip + quote-verify + ratio`.
