"""CI-guards (design principle #5): behavioral rules as executable checks.

1. Единый провайдер: никакой прямой LLM-SDK за пределами aeon/llm/
   (аудит 2026-10-14: 15 call-sites — все через DeepSeekClient → provider).
2. `except: pass` запрещено (honesty rule).
3. Бюджет-дефолт клиента — 4000 (site-класс «забыли масштабировать»).
"""

import ast
import json as _json
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parent.parent
AEON = REPO / "aeon"
LLM_PKG = AEON / "llm"


def test_no_direct_llm_sdk_outside_llm_package():
    """Прямой SDK-доступ (chat.completions / OpenAI()) — только в aeon/llm/."""
    offenders = []
    for path in sorted(AEON.rglob("*.py")):
        if LLM_PKG in path.parents:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "chat.completions" in line or "OpenAI(" in line:
                offenders.append(f"{path.relative_to(REPO)}:{number}")
    assert offenders == [], f"direct SDK outside aeon/llm/: {offenders}"


def test_no_bare_except_pass():
    """`except ...: pass` — запрещено для нового кода.

    Frozen baseline (reviewed-intentional, 2026-10-14): json_repair ×3 —
    последовательные стратегии repair («не сработала → следующая»);
    refactor в strategy-loop — backlog Ф4. Любой НОВЫЙ offender → fail.
    """
    baseline_intentional = {
        r"aeon\llm\json_repair.py:65",
        r"aeon\llm\json_repair.py:74",
        r"aeon\llm\json_repair.py:82",
    }
    offenders = set()
    for path in sorted(AEON.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    offenders.add(f"{path.relative_to(REPO)}:{node.lineno}")
    new_offenders = offenders - baseline_intentional
    assert new_offenders == set(), f"NEW bare except:pass: {sorted(new_offenders)}"


class _StubCompletions:
    def __init__(self, content):
        self.content = content
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content=self.content),
                finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        )


def test_call_json_default_budget_is_4000():
    """Аудит 2026-10-14: default budget 4000 (было 2000 — truncation-класс)."""
    from aeon.llm_client import DeepSeekClient

    client = DeepSeekClient(api_key="test-key")
    completions = _StubCompletions(_json.dumps({"ok": True}))
    client._provider._client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions))

    result = client._call_json([{"role": "user", "content": "x"}])

    assert result == {"ok": True}
    assert completions.last_kwargs["max_tokens"] == 4000
