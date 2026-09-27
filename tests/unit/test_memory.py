"""Behaviour: a thread remembers earlier turns, and the prompt keeps only the last six."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from bas_assistant.agent.prompts import build_messages
from bas_assistant.agent.state import AgentState, Turn, UserContext
from tests.graph_fakes import FakeProxy, answer_json, ask

pytestmark = pytest.mark.unit

_SUPPORT = {"X-Demo-Role": "support"}


def test_follow_up_question_sees_the_previous_turn(client: TestClient, proxy: FakeProxy) -> None:
    thread_id = ask(client, "What does the sample controller draw?").json()["thread_id"]

    ask(client, "And at 120 VAC?", thread_id=thread_id)

    follow_up = proxy.answer_calls()[1]["messages"]
    assert follow_up[1] == {"role": "user", "content": "What does the sample controller draw?"}
    assert follow_up[2] == {
        "role": "assistant",
        "content": "The sample controller draws 4 W at 24 VAC.",
    }


def test_thread_history_lists_turns_in_order(client: TestClient, proxy: FakeProxy) -> None:
    proxy.answers = [answer_json(answer="First."), answer_json(answer="Second.")]
    thread_id = ask(client, "one").json()["thread_id"]
    ask(client, "two", thread_id=thread_id)

    history = client.get(f"/threads/{thread_id}/history", headers=_SUPPORT).json()

    assert history == [
        {"question": "one", "answer": "First."},
        {"question": "two", "answer": "Second."},
    ]


def test_cached_answer_still_starts_the_thread_history(client: TestClient) -> None:
    ask(client, "Power draw?")
    cached = ask(client, "Power draw?").json()

    history = client.get(f"/threads/{cached['thread_id']}/history", headers=_SUPPORT).json()

    assert cached["cache_hit"] is True
    assert history == [{"question": "Power draw?", "answer": cached["answer"]}]


def test_unknown_thread_is_404(client: TestClient) -> None:
    assert client.get(f"/threads/{uuid4()}/history", headers=_SUPPORT).status_code == 404
    assert ask(client, "hi", thread_id=str(uuid4())).status_code == 404


def test_another_roles_thread_cannot_be_continued_or_read(client: TestClient) -> None:
    thread_id = ask(client, "Engineer-only wiring detail?", role="engineer").json()["thread_id"]

    follow_up = ask(client, "And the rest?", role="support", thread_id=thread_id)
    history = client.get(f"/threads/{thread_id}/history", headers=_SUPPORT)

    assert (follow_up.status_code, history.status_code) == (404, 404)


def test_thread_history_without_a_role_is_read_as_support(client: TestClient) -> None:
    thread_id = ask(client, "Engineer-only wiring detail?", role="engineer").json()["thread_id"]
    assert client.get(f"/threads/{thread_id}/history").status_code == 404


def test_prompt_keeps_only_the_last_six_turns() -> None:
    user = UserContext(id=uuid4(), role="support", acl_groups=["all"], tools_allowed=[])
    history = [Turn(question=f"q{n}", answer=f"a{n}") for n in range(8)]
    state = AgentState(request_id=uuid4(), question="now", user=user, history=history)

    messages = build_messages(state)

    questions = [m["content"] for m in messages[1:-1] if m["role"] == "user"]
    assert questions == ["q2", "q3", "q4", "q5", "q6", "q7"]
