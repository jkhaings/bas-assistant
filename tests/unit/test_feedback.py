"""Behaviour: answer feedback and flags are stored per request, for its owner only."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY
from sqlalchemy import Engine, select

from bas_assistant.db.activity import Feedback, Flag
from tests.graph_fakes import ask

pytestmark = pytest.mark.unit


def _request_id(client: TestClient, role: str = "support") -> str:
    request_id: str = ask(client, "How much power does the sample controller draw?", role).json()[
        "request_id"
    ]
    return request_id


def _feedback_values(engine: Engine) -> list[str]:
    with engine.connect() as conn:
        return list(conn.execute(select(Feedback.value)).scalars())


def test_feedback_is_stored_for_the_request(client: TestClient, engine: Engine) -> None:
    request_id = _request_id(client)

    response = client.post(
        f"/requests/{request_id}/feedback",
        json={"value": "used_as_is"},
        headers={"X-Demo-Role": "support"},
    )

    assert response.status_code == 204
    assert _feedback_values(engine) == ["used_as_is"]


def test_a_second_vote_replaces_the_first(client: TestClient, engine: Engine) -> None:
    request_id = _request_id(client)
    for value in ("used_as_is", "used_with_edits"):
        client.post(
            f"/requests/{request_id}/feedback",
            json={"value": value},
            headers={"X-Demo-Role": "support"},
        )

    assert _feedback_values(engine) == ["used_with_edits"]


def test_feedback_is_counted_in_metrics(client: TestClient) -> None:
    before = REGISTRY.get_sample_value("bas_feedback_total", {"value": "not_used"}) or 0.0
    request_id = _request_id(client)

    client.post(
        f"/requests/{request_id}/feedback",
        json={"value": "not_used"},
        headers={"X-Demo-Role": "support"},
    )

    assert REGISTRY.get_sample_value("bas_feedback_total", {"value": "not_used"}) == before + 1


def test_unknown_feedback_value_is_rejected(client: TestClient) -> None:
    request_id = _request_id(client)

    response = client.post(
        f"/requests/{request_id}/feedback",
        json={"value": "loved_it"},
        headers={"X-Demo-Role": "support"},
    )

    assert response.status_code == 422


def test_another_roles_request_is_not_found(client: TestClient, engine: Engine) -> None:
    request_id = _request_id(client, role="engineer")

    response = client.post(
        f"/requests/{request_id}/feedback",
        json={"value": "not_used"},
        headers={"X-Demo-Role": "support"},
    )

    assert response.status_code == 404
    assert _feedback_values(engine) == []


def test_an_unknown_request_is_not_found(client: TestClient) -> None:
    response = client.post(f"/requests/{uuid4()}/flag", json={"reason": "wrong voltage"})

    assert response.status_code == 404


def test_a_flag_is_stored_with_its_reason_redacted(client: TestClient, engine: Engine) -> None:
    request_id = _request_id(client)

    response = client.post(
        f"/requests/{request_id}/flag",
        json={"reason": "Says 4 W but the sheet says 6 W, ask jane.doe@example.com"},
        headers={"X-Demo-Role": "support"},
    )

    assert response.status_code == 204
    with engine.connect() as conn:
        reasons = list(conn.execute(select(Flag.reason)).scalars())
    assert reasons == ["Says 4 W but the sheet says 6 W, ask [REDACTED]"]


def test_an_empty_flag_reason_is_rejected(client: TestClient) -> None:
    request_id = _request_id(client)

    response = client.post(f"/requests/{request_id}/flag", json={"reason": ""})

    assert response.status_code == 422
