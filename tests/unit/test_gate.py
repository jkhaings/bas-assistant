"""Behaviour: a proposed ticket pauses the graph until an admin with the token decides."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import Engine, select

from bas_assistant.agent.nodes import NO_TICKET_NOTE
from bas_assistant.db.activity import Audit, Request
from tests.graph_fakes import ADMIN_TOKEN, FakeProxy, answer_json, ask

pytestmark = pytest.mark.unit

_ADMIN = {"X-Admin-Token": ADMIN_TOKEN}


def _ask_for_ticket(client: TestClient, proxy: FakeProxy, role: str = "engineer") -> dict[str, Any]:
    """The decoded /ask response body."""
    proxy.answers = [answer_json(answer="I drafted a ticket.", ticket_title="Replace controller")]
    body: dict[str, Any] = ask(client, "Please open a ticket for a new controller", role).json()
    return body


def test_ticket_request_pauses_for_approval(client: TestClient, proxy: FakeProxy) -> None:
    body = _ask_for_ticket(client, proxy)

    assert body["decision"] == "paused"
    assert body["approval_required"] is True
    tickets = client.get("/tickets", headers=_ADMIN).json()
    assert [(t["id"], t["status"]) for t in tickets] == [(body["ticket_id"], "proposed")]
    assert tickets[0]["draft"]["title"] == "Replace controller"


def test_approve_without_the_admin_token_is_401(client: TestClient, proxy: FakeProxy) -> None:
    thread_id = _ask_for_ticket(client, proxy)["thread_id"]

    response = client.post("/approve", json={"thread_id": thread_id, "approve": True})

    assert response.status_code == 401
    assert client.get("/tickets", headers=_ADMIN).json()[0]["status"] == "proposed"


def test_approve_with_a_wrong_token_is_401(client: TestClient, proxy: FakeProxy) -> None:
    thread_id = _ask_for_ticket(client, proxy)["thread_id"]

    response = client.post(
        "/approve",
        json={"thread_id": thread_id, "approve": True},
        headers={"X-Admin-Token": "guess"},
    )

    assert response.status_code == 401


def test_ticket_list_needs_the_admin_token(client: TestClient) -> None:
    assert client.get("/tickets").status_code == 401


def test_approval_with_the_token_resumes_the_graph_and_files_the_ticket(
    client: TestClient, proxy: FakeProxy, engine: Engine
) -> None:
    asked = _ask_for_ticket(client, proxy)

    response = client.post(
        "/approve", json={"thread_id": asked["thread_id"], "approve": True}, headers=_ADMIN
    )

    assert response.json() == {
        "thread_id": asked["thread_id"],
        "ticket_id": asked["ticket_id"],
        "status": "filed",
    }
    ticket = client.get("/tickets", headers=_ADMIN).json()[0]
    assert ticket["status"] == "filed"
    assert ticket["approver_id"] is not None
    with engine.connect() as conn:
        actions: list[str] = list(
            conn.execute(select(Audit.action).order_by(Audit.created_at)).scalars()
        )
        decision: str | None = conn.execute(select(Request.decision)).scalar_one()
    assert actions == ["ticket_proposed", "ticket_approved", "ticket_filed"]
    assert decision == "answered"


def test_rejection_leaves_the_ticket_rejected(client: TestClient, proxy: FakeProxy) -> None:
    thread_id = _ask_for_ticket(client, proxy)["thread_id"]

    response = client.post(
        "/approve", json={"thread_id": thread_id, "approve": False}, headers=_ADMIN
    )

    assert response.json()["status"] == "rejected"
    assert client.get("/tickets", headers=_ADMIN).json()[0]["status"] == "rejected"


def test_support_role_cannot_create_tickets(client: TestClient, proxy: FakeProxy) -> None:
    body = _ask_for_ticket(client, proxy, role="support")

    assert body["decision"] == "answered"
    assert body["ticket_id"] is None
    assert body["notes"] == [NO_TICKET_NOTE]
    assert client.get("/tickets", headers=_ADMIN).json() == []


def test_support_role_prompt_never_mentions_creating_tickets(
    client: TestClient, proxy: FakeProxy
) -> None:
    ask(client, "Power draw?", role="support")
    ask(client, "Power draw?", role="engineer")

    support_system, engineer_system = (
        call["messages"][0]["content"] for call in proxy.answer_calls()
    )
    assert "fill ticket_draft" not in support_system
    assert "fill ticket_draft" in engineer_system


def test_new_question_on_a_paused_thread_is_409(client: TestClient, proxy: FakeProxy) -> None:
    thread_id = _ask_for_ticket(client, proxy)["thread_id"]

    assert ask(client, "Another question", "engineer", thread_id).status_code == 409


def test_approve_on_a_thread_without_a_pending_ticket_is_409(client: TestClient) -> None:
    thread_id = ask(client, "Power draw?").json()["thread_id"]

    response = client.post(
        "/approve", json={"thread_id": thread_id, "approve": True}, headers=_ADMIN
    )

    assert response.status_code == 409


def test_second_approval_while_one_is_in_progress_is_409(
    client: TestClient, proxy: FakeProxy, redis: Redis
) -> None:
    thread_id = _ask_for_ticket(client, proxy)["thread_id"]
    redis.set(f"approve:{thread_id}", "1")

    response = client.post(
        "/approve", json={"thread_id": thread_id, "approve": True}, headers=_ADMIN
    )

    assert response.status_code == 409
    assert client.get("/tickets", headers=_ADMIN).json()[0]["status"] == "proposed"


def test_a_second_ticket_on_the_same_thread_can_be_approved_right_away(
    client: TestClient, proxy: FakeProxy
) -> None:
    first = _ask_for_ticket(client, proxy)
    client.post("/approve", json={"thread_id": first["thread_id"], "approve": True}, headers=_ADMIN)
    proxy.answers = [answer_json(answer="Drafted again.", ticket_title="Second part")]
    ask(client, "And a ticket for the second unit", "engineer", first["thread_id"])

    response = client.post(
        "/approve", json={"thread_id": first["thread_id"], "approve": True}, headers=_ADMIN
    )

    assert response.json()["status"] == "filed"
    statuses = [t["status"] for t in client.get("/tickets", headers=_ADMIN).json()]
    assert statuses == ["filed", "filed"]
