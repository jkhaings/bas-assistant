"""Behaviour: every request records the prompt version, the retriever always filters by the
role's own ACL groups, and a prompt change invalidates cached answers."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from bas_assistant.agent.prompts import PROMPT_VERSION
from bas_assistant.agent.state import UserContext, turn_input
from bas_assistant.agent.turn import thread_config
from bas_assistant.cost.cache import cache_key
from bas_assistant.db.activity import Request
from bas_assistant.runtime import AppRuntime
from tests.graph_fakes import ask

pytestmark = pytest.mark.unit


def test_each_request_records_the_prompt_version(client: TestClient, engine: Engine) -> None:
    ask(client, "Power draw?")

    with engine.connect() as conn:
        assert conn.execute(select(Request.prompt_version)).scalar_one() == PROMPT_VERSION


def test_a_new_prompt_version_misses_the_old_cached_answer() -> None:
    assert cache_key("Power?", "support", "1", "aaa") != cache_key("Power?", "support", "1", "bbb")


def test_a_user_context_wider_than_its_role_never_reaches_the_retriever(
    runtime: AppRuntime,
) -> None:
    widened = UserContext(
        id=uuid4(), role="support", acl_groups=["all", "engineer"], tools_allowed=[]
    )

    with pytest.raises(PermissionError):
        runtime.graph.invoke(
            turn_input(uuid4(), "Power draw?", widened),
            thread_config(uuid4()),
            context=runtime.agent,
        )
