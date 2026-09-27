"""Behaviour: a demo role maps to ACL groups, or is rejected."""

import pytest
from fastapi import HTTPException

from bas_assistant.api.roles import Role, acl_groups_for_role, demo_role

pytestmark = pytest.mark.unit


def test_support_sees_only_public_documents() -> None:
    assert acl_groups_for_role(Role.SUPPORT) == ["all"]


def test_engineer_and_admin_also_see_engineer_documents() -> None:
    assert "engineer" in acl_groups_for_role(Role.ENGINEER)
    assert "engineer" in acl_groups_for_role(Role.ADMIN)


def test_demo_role_parses_a_known_role() -> None:
    assert demo_role("engineer") == Role.ENGINEER


def test_demo_role_rejects_an_unknown_role() -> None:
    with pytest.raises(HTTPException) as exc_info:
        demo_role("hacker")
    assert exc_info.value.status_code == 422
