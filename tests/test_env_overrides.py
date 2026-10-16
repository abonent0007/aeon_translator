"""Тесты env-override внешних endpoint-констант (HARD-001..004, maintenance-аудит).

Executable guards (design principle #23): константы читаются на import-времени,
поэтому override проверяется в изолированном subprocess; default — in-process.
"""

import os
import subprocess
import sys
from pathlib import Path

from aeon.image_gen import FluxImageGenerator

REPO = Path(__file__).resolve().parent.parent


def _probe(code: str, **env_overrides) -> str:
    run_env = dict(os.environ)
    run_env.update({key: str(value) for key, value in env_overrides.items()})
    run_env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run([sys.executable, "-c", code], cwd=REPO,
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", env=run_env, timeout=120)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().splitlines()[-1]


def test_wikidata_api_url_env_override():
    line = _probe("from aeon.entity_linking import API_URL; print(API_URL)",
                  AEON_WIKIDATA_API_URL="http://staging-wd.example/api")
    assert line == "http://staging-wd.example/api"


def test_pleiades_url_template_env_override():
    line = _probe(
        "from aeon.crosswalk import PLEIADES_URL_TEMPLATE; "
        "print(PLEIADES_URL_TEMPLATE)",
        AEON_PLEIADES_URL_TEMPLATE="http://staging-pl.example/{pid}")
    assert line == "http://staging-pl.example/{pid}"


def test_flux_status_url_env_override():
    line = _probe(
        "from aeon.image_gen import FluxImageGenerator as F; "
        "print(F(api_key='x').status_url)",
        FLUX_STATUS_URL="http://staging-flux.example/get")
    assert line == "http://staging-flux.example/get"


def test_flux_timeout_env_override_and_default(monkeypatch):
    override = _probe(
        "from aeon.image_gen import FluxImageGenerator as F; "
        "print(F(api_key='x').timeout)",
        FLUX_TIMEOUT_SEC="7")
    assert override == "7.0"
    monkeypatch.delenv("FLUX_TIMEOUT_SEC", raising=False)
    assert FluxImageGenerator(api_key="x").timeout == 30.0
