"""Behaviour: one IP gets a fixed number of requests per minute, whatever role it claims, and
every limit answers in one shape the UI can show, with an audit row."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from redis import Redis
from sqlalchemy import Engine, func, insert, select

from bas_assistant.db.activity import Audit, Request, Thread, Usage
from bas_assistant.guardrails.limits import MESSAGES, RATE_WINDOW, attempts_in_window
from bas_assistant.runtime import AppRuntime
from tests.graph_fakes import FakeProxy, ask, make_client

pytestmark = pytest.mark.unit


def _actions(engine: Engine) -> list[str]:
    with engine.connect() as conn:
        return list(conn.execute(select(Audit.action).order_by(Audit.created_at)).scalars())


def test_one_ip_is_limited_across_roles(runtime: AppRuntime) -> None:
    client = make_client(replace(runtime, ip_rate_limit=3))
    statuses = [
        ask(client, "Power draw?", role=role).status_code
        for role in ("support", "engineer", "admin", "support")
    ]

    assert statuses == [200, 200, 200, 429]


def test_rate_limited_response_says_when_to_retry(runtime: AppRuntime) -> None:
    client = make_client(replace(runtime, ip_rate_limit=1))
    ask(client, "Power draw?")

    response = ask(client, "Power draw?")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == str(RATE_WINDOW.seconds)
    detail = response.json()["detail"]
    assert (detail["reason"], detail["message"]) == ("rate_limited", MESSAGES["rate_limited"])
    assert detail["resets_at"] is not None


def test_a_burst_is_audited_once(runtime: AppRuntime, engine: Engine) -> None:
    client = make_client(replace(runtime, ip_rate_limit=1))
    for _ in range(4):
        ask(client, "Power draw?")

    assert _actions(engine).count("rate_limited") == 1


def test_attempts_older_than_the_window_stop_counting(redis: Redis) -> None:
    start = datetime(2026, 9, 27, 12, tzinfo=UTC)
    for second in range(3):
        attempts_in_window(redis, "ratelimit:test", start + timedelta(seconds=second))

    later = start + RATE_WINDOW + timedelta(seconds=1, milliseconds=500)

    assert attempts_in_window(redis, "ratelimit:test", later) == 2


def test_daily_cap_answers_with_a_message_and_is_audited(
    runtime: AppRuntime, engine: Engine
) -> None:
    with engine.begin() as conn:
        conn.execute(
            insert(Usage).values(
                stage="answer",
                alias="strong",
                model="m",
                provider="p",
                input_tokens=1,
                usd=Decimal(5),
                latency_ms=1,
                created_at=datetime.now(UTC),
            )
        )
    client = make_client(runtime)

    response = ask(client, "Power draw?")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["message"] == MESSAGES["daily_budget_reached"]
    assert "Retry-After" in response.headers
    assert "daily_cap_reached" in _actions(engine)


def test_used_allowance_is_audited(runtime: AppRuntime, engine: Engine) -> None:
    client = make_client(replace(runtime, user_daily_questions=1))
    ask(client, "First question?")

    response = ask(client, "Second question?")

    assert response.json()["detail"]["message"] == MESSAGES["daily_allowance_used"]
    assert "allowance_used" in _actions(engine)


def test_a_spent_virtual_key_is_429_and_does_not_use_up_the_question(
    runtime: AppRuntime, proxy: FakeProxy
) -> None:
    client = make_client(replace(runtime, user_daily_questions=1))
    proxy.budget_spent = True

    response = ask(client, "Power draw?")
    proxy.budget_spent = False

    assert response.status_code == 429
    assert response.json()["detail"]["reason"] == "key_budget_reached"
    assert ask(client, "Power draw?").status_code == 200


def test_a_rate_limited_request_writes_no_request_or_thread_row(
    runtime: AppRuntime, engine: Engine
) -> None:
    client = make_client(replace(runtime, ip_rate_limit=1))
    ask(client, "Power draw?")

    ask(client, "Power draw?")

    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(Request)).scalar_one() == 1
        assert conn.execute(select(func.count()).select_from(Thread)).scalar_one() == 1


def test_a_spent_virtual_key_mid_stream_sends_a_key_budget_error(
    runtime: AppRuntime, proxy: FakeProxy
) -> None:
    client = make_client(runtime)
    proxy.budget_spent = True

    response = client.post("/ask/stream", json={"question": "Power draw?"})

    last = response.text.strip().split("\n\n")[-1]
    assert "event: error" in last
    assert "key_budget_reached" in last
