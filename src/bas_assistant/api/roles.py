"""Demo role switcher: the X-Demo-Role header maps to ACL groups.

Roles come from SSO in production; the demo has no login.
"""

from __future__ import annotations

from enum import StrEnum

from fastapi import Header, HTTPException

_ACL_GROUPS: dict[str, list[str]] = {
    "support": ["all"],
    "engineer": ["all", "engineer"],
    "admin": ["all", "engineer"],
}


_TOOLS: dict[str, list[str]] = {
    "support": [],
    "engineer": ["create_ticket"],
    "admin": ["create_ticket"],
}


class Role(StrEnum):
    """A demo role, set by the X-Demo-Role header."""

    SUPPORT = "support"
    ENGINEER = "engineer"
    ADMIN = "admin"


def acl_groups_for_role(role: Role) -> list[str]:
    """Return the ACL groups a role can see."""
    return _ACL_GROUPS[role.value]


def tools_for_role(role: Role) -> list[str]:
    """Return the tools a role may use; the model never hears about the others."""
    return _TOOLS[role.value]


def demo_role(x_demo_role: str = Header(default=Role.SUPPORT.value, alias="X-Demo-Role")) -> Role:
    """Parse X-Demo-Role, defaulting to support when absent, 422 on an unknown role."""
    try:
        return Role(x_demo_role)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"unknown role: {x_demo_role}") from None
