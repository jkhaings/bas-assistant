"""Behaviour: GET /healthz returns {"status": "ok"}."""

import pytest
from fastapi.testclient import TestClient

from bas_assistant.main import app

pytestmark = pytest.mark.unit

_client = TestClient(app)


def test_healthz_returns_ok() -> None:
    response = _client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
