# Skill Observation Log

**Project:** aeon_translator (`C:\Users\User\Documents\aeon_translator-main\aeon_translator-main`)
**Created:** 2026-10-14

---

### Observation 1: Кураторские чек-поинты переопределяют автономный режим оркестратора

**Date:** 2026-10-14
**Session context:** AEON v4.0 — планирование и старт Фазы 0/1. Пользователь выступает куратором: требует фиксированный формат отчёта по каждому шагу и стоп-точки для верификации.
**Skill:** task-orchestrator
**Type:** internal
**Phase/Area:** Phase 4 (Autonomous Execution) — конфликт с пользовательским протоколом курирования

**Issue:** Skill декларирует «No other waits. Execute all steps autonomously», однако пользователь явно задал пошаговые чек-поинты с форматом отчёта (git log/status/scan после 0.1; pytest+метрики после 0.2 и т.д.). Без явного правила приоритета автономный режим может проигнорировать пользовательский протокол верификации.

**Suggested improvement:** В Hard Rules добавить: «Если пользователь задал явные шаговые чек-поинты и формат отчёта — они переопределяют автономный режим; остановиться на каждом чек-поинте и дать отчёт в запрошенном формате».

**Principle:** Явный пользовательский протокол верификации сильнее дефолтной автономности скилла; шаговые отчёты — часть acceptance criteria фазы.

---

### Observation 2: Старт исполнения после Plan Mode требует сидирования состояния из утверждённого плана

**Date:** 2026-10-14
**Session context:** План был согласован в Plan Mode (read-only), где `.opencode/orchestrator_state.json` создать невозможно. При переключении в Build состояние создавалось вручную из текста плана.
**Skill:** task-orchestrator
**Type:** internal
**Phase/Area:** Sleep/Wake Protocol / Phase 1 (Orchestration)

**Issue:** При переходе Plan → Build оркестратор стартует «с нуля», хотя план уже утверждён (включая кураторские дельты). Риск потери согласованных решений при повторном enrichment.

**Suggested improvement:** Добавить сценарий «seeding from approved plan»: если в сессии существует утверждённый план — при активации записывать его в state (plan[], user_preferences, deltas) без повторной Phase 1.

**Principle:** Утверждённый в read-only фазе план должен переноситься в исполняемое состояние без потери решений.
