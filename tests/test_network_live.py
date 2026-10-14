"""Live-тесты под маркером network (по умолчанию исключены из прогона).

Запуск: pytest -m network -k pleiades -v
Назначение: проверка реальных схем внешних API, недоступных из dev-сети.
"""

import pytest
import requests

LIVE_USER_AGENT = {"User-Agent": "AEON-Translator/4.0 (research)"}


@pytest.mark.network
def test_pleiades_live_schema():
    """Схема Pleiades places/<id>/json (документированные поля)."""
    url = "https://pleiades.stoa.org/places/579885/json"
    try:
        response = requests.get(url, headers=LIVE_USER_AGENT, timeout=25)
    except requests.RequestException as exc:
        pytest.skip(f"Pleiades недоступен из этой сети: {exc}")

    assert response.status_code == 200
    payload = response.json()
    for key in ("id", "uri", "title", "placeTypes", "reprPoint"):
        assert key in payload, f"в схеме Pleiades нет ожидаемого поля: {key}"
    assert str(payload.get("id")) == "579885"
