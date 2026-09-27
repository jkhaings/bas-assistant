"""Integration behaviour: every dashboard view runs on real Postgres; grafana_reader can read
the panel views but not the tables or dash_questions (migration 0005); the two cover-letter
percentages count each answered question once."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, create_engine, insert, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from bas_assistant.db.activity import Feedback, Flag, Request, Thread
from bas_assistant.settings import Settings

pytestmark = pytest.mark.integration

PANEL_VIEWS = (
    "dash_spend_today",
    "dash_spend_month",
    "dash_cost_daily",
    "dash_cost_by_model_stage",
    "dash_cost_by_user",
    "dash_cache_daily",
    "dash_decisions_daily",
    "dash_latency_hourly",
    "dash_adoption_weekly",
    "dash_tickets_daily",
    "dash_tickets_status",
    "dash_feedback_weekly",
    "dash_flags_weekly",
    "dash_eval_latest",
)


@pytest.fixture
def conn() -> Iterator[Connection]:
    """A connection as the app's owner role, rolled back afterwards."""
    engine = create_engine(Settings().database_url)
    with engine.connect() as connection:
        yield connection
        connection.rollback()
    engine.dispose()


@pytest.fixture
def as_reader(conn: Connection) -> Connection:
    conn.execute(text("SET ROLE grafana_reader"))
    return conn


@pytest.mark.parametrize("view", PANEL_VIEWS)
def test_grafana_reader_can_select_each_panel_view(as_reader: Connection, view: str) -> None:
    as_reader.execute(text(f"SELECT * FROM {view}")).all()


@pytest.mark.parametrize("relation", ["dash_questions", "requests", "usage", "flags", "users"])
def test_grafana_reader_cannot_read_ids_or_tables(as_reader: Connection, relation: str) -> None:
    with pytest.raises(ProgrammingError, match="permission denied"):
        as_reader.execute(text(f"SELECT * FROM {relation}"))


def test_grafana_reader_queries_time_out(as_reader: Connection) -> None:
    # SET ROLE does not apply the role's settings, so set what a real login would get.
    as_reader.execute(text("SET statement_timeout = '5s'"))
    with pytest.raises(OperationalError, match="statement timeout"):
        as_reader.execute(text("SELECT pg_sleep(6)"))


def test_grafana_reader_role_is_limited(conn: Connection) -> None:
    limit, config = conn.execute(
        text("SELECT rolconnlimit, rolconfig FROM pg_roles WHERE rolname = 'grafana_reader'")
    ).one()

    assert limit == 5
    assert "statement_timeout=5s" in config


def _answered(conn: Connection, user_id: uuid.UUID, thread_id: uuid.UUID) -> uuid.UUID:
    request_id = uuid.uuid4()
    conn.execute(
        insert(Request).values(
            id=request_id,
            thread_id=thread_id,
            user_id=user_id,
            role="support",
            question_redacted="q",
            route="fast",
            decision="answered",
            latency_ms=1,
        )
    )
    return request_id


def _this_week(conn: Connection, view: str, column: str) -> int:
    value = conn.execute(
        text(f"SELECT {column} FROM {view} WHERE week = date_trunc('week', now(), 'UTC')")
    ).scalar_one_or_none()
    return int(value or 0)


def test_each_answer_counts_once_in_feedback_and_flags(conn: Connection) -> None:
    user_id: uuid.UUID = conn.execute(
        text("SELECT id FROM users WHERE role = 'support' LIMIT 1")
    ).scalar_one()
    thread_id = uuid.uuid4()
    conn.execute(insert(Thread).values(id=thread_id, user_id=user_id))
    counted = [
        ("dash_flags_weekly", "answered"),
        ("dash_flags_weekly", "flagged"),
        ("dash_feedback_weekly", "answered"),
        ("dash_feedback_weekly", "used_as_is"),
    ]
    before = [_this_week(conn, view, column) for view, column in counted]
    flagged_twice = _answered(conn, user_id, thread_id)
    _answered(conn, user_id, thread_id)
    conn.execute(
        insert(Flag),
        [{"request_id": flagged_twice, "reviewer_id": user_id, "reason": "r"} for _ in range(2)],
    )
    conn.execute(
        insert(Feedback).values(request_id=flagged_twice, user_id=user_id, value="used_as_is")
    )

    after = [_this_week(conn, view, column) for view, column in counted]

    # Two answers; one flagged twice counts as one flagged answer; one vote.
    assert [a - b for a, b in zip(after, before, strict=True)] == [2, 1, 2, 1]
