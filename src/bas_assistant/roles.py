"""Demo roles chosen by the "View as" switcher. In production these come from SSO."""

from typing import Literal

Role = Literal["support", "engineer", "admin"]

ACL_GROUPS: dict[Role, list[str]] = {
    "support": ["all"],
    "engineer": ["all", "engineer"],
    "admin": ["all", "engineer"],
}

TOOLS_ALLOWED: dict[Role, list[str]] = {
    "support": [],
    "engineer": ["create_ticket"],
    "admin": ["create_ticket"],
}
