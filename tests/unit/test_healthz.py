"""Behaviour: GET /healthz returns {"status": "ok"}; the web app is served beside the API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bas_assistant.main import app, create_app
from tests.graph_fakes import no_startup

pytestmark = pytest.mark.unit

_client = TestClient(app)


def test_healthz_returns_ok() -> None:
    response = _client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_the_web_app_is_served_at_the_root_beside_the_api(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<title>bas-assistant</title>")
    client = TestClient(create_app(no_startup, web_dist=tmp_path))

    page = client.get("/")

    assert page.headers["content-type"].startswith("text/html")
    assert "bas-assistant" in page.text
    assert client.get("/healthz").json() == {"status": "ok"}
