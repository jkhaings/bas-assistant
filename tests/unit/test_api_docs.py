"""Behaviour: /docs and /openapi.json are served only where API_DOCS switches them on."""

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from bas_assistant.main import create_app
from bas_assistant.settings import ApiDocsSettings
from tests.graph_fakes import no_startup

pytestmark = pytest.mark.unit

ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize("path", ["/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"])
def test_the_api_docs_are_not_served_unless_switched_on(path: str, tmp_path: Path) -> None:
    # The web build is mounted at / in the image, and a docs path must not fall through to it.
    (tmp_path / "index.html").write_text("<title>bas-assistant</title>")
    client = TestClient(create_app(no_startup, web_dist=tmp_path))

    assert client.get(path).status_code == 404


def test_the_api_docs_are_served_when_switched_on() -> None:
    client = TestClient(create_app(no_startup, api_docs=True))

    assert client.get("/docs").status_code == 200
    assert "/tickets" in client.get("/openapi.json").json()["paths"]


def test_api_docs_is_off_unless_the_environment_sets_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("API_DOCS", raising=False)
    assert ApiDocsSettings().api_docs is False

    monkeypatch.setenv("API_DOCS", "true")
    assert ApiDocsSettings().api_docs is True


def test_only_the_local_compose_file_switches_the_api_docs_on() -> None:
    local = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]["app"]
    prod = yaml.safe_load((ROOT / "docker-compose.prod.yml").read_text())["services"]["app"]

    assert local["environment"]["API_DOCS"] == "true"
    assert "API_DOCS" not in prod["environment"]
