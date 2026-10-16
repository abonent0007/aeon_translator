# Phase 3 Retrospective (draft C1 — 2026-10-16)

Статус: **draft до countersign C1**. Consolidation-правила: новые принципы
(#24+) не создаются; backlog не активируется; только факты.

## 1. Scope

**Планировалось (roadmap kickoff):** 3.1 `.aeon v2` → 3.5 variant readings →
3.3 gold-standard; 3.2 morphology (после 3.3+2.7); 3.6 web (после 2.7);
3.4/3.7/3.8 backlog.

**Сделано:** 3.1 ✅, 3.5 ✅, 3.3 ✅, 3.2 ✅, 3.4 ✅ (pilot, v1.2.1 final),
3.7 ✅ (export). **Отложено:** 3.6 (premature без спроса — решение
2026-10-16), 3.8 (calibration; trigger N≥30), 3.9 (embeddings; deferred).

## 2. Steps 3.1–3.7 — сводка

| Step | Что | Ключевые коммиты | Ключевое |
|---|---|---|---|
| 3.1 | `.aeon v2` формат | `50ea764` (+`d4ed91f` fixture, `164c0dc` contract-metadata 2b) | writer/reader/validator/versioning; mock-guard; v1-миграция (frozen fixture); D1–D4 |
| 3.5 | Variant readings | `1522365` (+`9e89dac` clarifications) | apparatus sidecar; LLM только ВЫБИРАЕТ; work-guard; detective mode `reading`; 27 тестов |
| 3.3 | Gold-standard corpus | `3218bed` (+`21e7c40`) | 28→(рост) аннотаций; stdlib-метрики; два уровня тестов (reports/baseline); RU-аудит fix |
| 3.2 | Morphology `morph_v1` | `45517a5`, `5f87b83` (baseline), `5e4125d` (1.1.1) | enum-synced contract; F1 0.90–0.99; Class A source-verified патчи; finish_reason-инфра |
| 3.4 | Crossrefs pilot | `9239b80`→`c21392f`→`6ee6dc5`→`ae60db3`→`0a4b801` | prompt v1.0→v1.2.1 (3 flip'а); gold 1.2.1 (+author_id); headline link-F1 0.800 |
| 3.6 | — (deferred) | — | premature (нет спроса/потребителей; export-вперёд — #22) |
| 3.7 | Export formats | `0de1663`→`be4ff4e`→`02e5eff` | TEI/MD/JSON-LD/BibTeX; детерминизм (AST-guard); gold-reject; H2 finding |

## 3. Baselines (consolidated)

| Метрика | Значение | Источник |
|---|---|---|
| Markers F1 (lacuna/supplement) | **1.00 / 1.00** | real t3/t4 |
| Entities F1 | **0.78** (P 0.65/R 0.97; t4, 49 atoms); 0.82 fold core-6 (t3) | t4 |
| Detective accuracy | **0.88** (t4; 0.75 t3) | t4 |
| Expert / Logician | **1.00 / 1.00** | t3/t4 |
| completeness MAE | **0.09** | t4 |
| Morphology F1 (pos/lemma/tense/mood/voice/person/case/number/gender) | **0.98/0.92/0.96/0.98/0.93/0.90/0.99/0.99/0.98** | morph_t4 |
| Crossref **headline link-F1** | **0.800** (kind-macro 0.619 — diagnostic) | v1.2.1 pilot |
| Gold-корпус | 54 атома / 15 текстов; schema 1.2.1 | gold/ |
| Suite / coverage | **476 passed / 92%** (3411 stmts) | fresh 2026-10-16 |
| Cost | t3 $0.0189 / morph $0.0214 / crossrefs $0.037 за 105-парый прогон | real_runs |

## 4. Design principles #1–#23 (сводная таблица)

| # | Принцип | Рождён | Статус |
|---|---|---|---|
| 1 | `finish_reason` проверяется во всех LLM-вызовах | 3.2 | ACTIVE (guard) |
| 2 | enum → минимум один few-shot на категорию *(в AGENTS исторически без номера — канонизируется здесь)* | 3.2 | ACTIVE |
| 3 | gold — не догма (source-verified патчи) | 3.2 | ACTIVE |
| 4 | F1 всегда с gold-diff | 3.2 | ACTIVE |
| 5 | behavioral rule → CI-guard | maintenance | ACTIVE |
| 6 | behavioral scans — AST, не regex | maintenance | ACTIVE |
| 7 | architectural choice — после эмпирического теста | 3.4 | ACTIVE |
| 8 | coverage gaps — explicit | 3.4 | ACTIVE |
| 9 | schema-инварианты программно в countersign | 3.4 | ACTIVE (×4) |
| 10 | validators before write | 3.4.1 | ACTIVE |
| 11 | absence of engine ≠ 0.00 | 3.4.1 | ACTIVE |
| 12 | few-shot учит демонстрацией (типичный, не минимальный) | 3.4.2 | ACTIVE |
| 13 | fix the rule, not the example | 3.4.2 | ACTIVE |
| 14 | confidence-scale = сила свидетельства | 3.4.2 | ACTIVE |
| 15 | phase completion = committed state + CI-check | 3.4.2 | ACTIVE (guard) |
| 16 | kind priority contextual (specificity, не размер) | 3.4.2 | candidate |
| 17 | LLM output → ground-truth filter | 3.4.2 | candidate (impl: post-filter) |
| 18 | infra idempotent OR fail-on-unexpected | 3.4.2 | ACTIVE (guard) |
| 19 | inter-kind rules → explicit exceptions | 3.4.2 | candidate (impl: D5/D7) |
| 20 | повторный whack-a-mole → неверная рамка | 3.4.2 | candidate (impl: link-level) |
| 21 | verify trigger — signal, не artifact | 3.4.2 | ACTIVE |
| 22 | publishable ≠ public: export до UI | 3.7 | candidate (impl: 3.7) |
| 23 | behavioral invariants → executable guards | 3.7 | ACTIVE (×3) |

**Явный список статусов:** **ACTIVE: #1–#15, #18, #21, #23 (18)**;
**candidate: #16, #17, #19, #20, #22 (5)**. Все пять candidate имеют
impl-свидетельство (D2/D3-приоритет, post-filter, explicit-exceptions D5→D7,
link-level reframing, 3.7-export); промоция — при повторном применении или
решением куратора. **#2 канонизирован как ACTIVE** — работал на 2.4/3.2
(ранее в AGENTS был без номера; это нумерация, не новый принцип).

## 5. Backlog (единая таблица, trigger-gated)

| Item | Trigger | Priority |
|---|---|---|
| **F4 gold expansion** (+ calibration 3.8, N≥30) | публикационные claims / ревизия | **HIGH** |
| contract v1.1 (Rule 3 content-first, Rule 5 emphasis) | new failing case | LOW |
| 3.6 Web UI/API | export demand (внешние потребители) | MEDIUM |
| `v2_markers_persistence` (H2, MEDIUM finding) | TEI-marker demand / marker re-audit | MEDIUM |
| `crossref_source_work_disambiguation` (#3-класс) | Ф4 | MEDIUM |
| `crossref_chronology_aware_harness` | corpus >30 текстов | LOW |
| gold bucket-drift revision (il×vergil) | Ф4 (gold revision) | LOW |
| 3.9 embeddings-provider | Ф4 scope-решение (multi-hop/семантический поиск) | LOW |
| `call_structured` (dynamic budget/cursor) | Ф4 (unbounded-array кейс, напр. linguistics 124 findings) | LOW |
| json_repair strategy-loop | repair-инцидент класса extractor-fallback (event) | LOW |
| `deepseek-chat` compatibility audit | deprecation-анонс провайдера (event) | LOW |
| legacy façade (`deepseek.py`) deprecation | следующий major-релиз (event) | LOW |
| RIS-format export | внешний запрос формата (demand) | LOW |
| crossref offset loci | потребитель запросит passage-level точность (demand) | LOW |
| kind-confidence | crossrefs N≥20 (datapoint-масштаб) | LOW |
| multi-hop chains | Ф4 | LOW |

## 6. Known gaps (consolidated)

- **3.4:** bucket-drift il×vergil (gold medium/pre-scale vs engine high); #3
  wrong-source FP (accepted, N=1); #7 livius→vergil (candidate, без consensus);
  direction-sensitivity harness (не влияет на headline); post-filter suppletive/
  ῥοή-коллизии (метрически нейтральны); direct_citation ×0 gold; echo×medium n=1;
  adaptation×medium 0.
- **3.2:** pronoun-person gap (person 0.90); zero-gold artifacts (papyrus/sappho);
  error classes A/B/C; enum→few-shot эмпирика.
- **3.7:** markers не в v2 (H2 MEDIUM); text_id/author отсутствуют в v2 (label-note);
  variant-renderer generic до интеграции selector.
- **Общие:** Pleiades README links (network); Trismegistos (нет датасета);
  role-consistency 10.7%; порог 0.85 не калиброван (N<30).

## 6b. What didn't work / was abandoned

- **D5 (3.4 v1.2):** translation-exception overfired (LLM hallucinated
  clause-by-clause correspondence для Vergil) → заменён D7 в v1.2.1.
  Урок: онтологический критерий (version-of-source) устойчивее лексического,
  когда LLM галлюцинирует evidence.
- **Cache-эффект:** 2.2% hit-rate (5.4K/244K) vs ожидание ≥30% — низкий
  prefix-reuse в pair-промпте. Backlog (не оптимизировали).
- **PowerShell double-execution:** pipeline-опечатка выполнила 105-прогон
  дважды (−$0.037) → #18 (overwrite-guard) + operator-дисциплина.
- **Pre-commit буква vs дух (3.4.2):** триггер «livius в echo» сработал на
  direction-artifact, не на kind-flip → реформирован через #21 (signal-not-artifact).
- **`meaning_hash` legacy-warning false-positive:** эмпирика Plato (стоп №3) —
  поле рутинное; триггер сужен до `legacy_v1_original` OR `contract != v1`.
- **Mock-span TEI:** Plato-mock не демонстрировал inline (RU-spans) — закрыто
  real-прогоном Sappho в той же сессии (не отложено).
- **contract v1.1 (Rule 3 content-first, Rule 5 emphasis):** активация
  отклонена — триггеры не сработали (failing case отсутствует). Не провал —
  отказ от активации без case (hygiene creep).
- **Trismegistos:** публичного датасета/API нет (SSL+403, datasets недоступны)
  → stub `no_public_dataset`; в pipeline не включается. Внешнее ограничение.
- **Pleiades offline dump:** ссылки README неверифицируемы из dev-сети
  (TCP ok, нет ответа) — dump отложен; live-skip в тестах. Внешнее ограничение.
- **Rule 2.1 «σ/ς-унификация, iota adscript»** — исследовано и сознательно
  отклонено (Unicode-стандарт): не баг, а зафиксированное решение против
  «поисковой унификации» в Ф3-пайплайне.

## 7. What we'd do differently (honest)

1. **Repo-integrity с первого дня шага:** данные 3.4.0 жили вне git до `1a869f8`
   (тесты шли на локальных файлах) → #15 + guard-тест родились из промаха.
2. **Метрика важнее правила на малом N:** 3 flip'а echo/adaptation (#20) —
   следовало переопределить headline на link-level РАНЬШЕ, не после третьего.
3. **Idempotency-гварды до первых платных прогонов:** двойной run (—$0.037, #18).
4. **Prompt-versioning в артефактах — с первого прогона** (v1.0-run остался без версии).
5. **Эмпирика на реальном файле — до спеки:** legacy/meaning_hash false-positive
   нашёлся только на стопе №3 (Plato-экспорт).
6. **#2-нумерация:** канонизировать сразу, не оставлять безымянный принцип.

## 8. Next decision

- **F4 (gold expansion + calibration)** — если планируются публикационные claims
  (N≥30 для калибровки 0.85) или внешняя ревизия.
- **3.6 (Web UI)** — если export (3.7) показал реальный спрос.
- **Pause** — проект в состоянии «research-grade tool»: завершённый
  исследовательский этап, publishable.

Критерии готовы; решение — за куратором.
