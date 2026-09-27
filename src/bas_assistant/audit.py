"""Append-only audit rows. Never store raw questions or PII in detail."""

from uuid import UUID

from sqlalchemy import Engine, insert

from bas_assistant.db import audit


def write_audit(
    engine: Engine, request_id: UUID | None, actor: str, action: str, detail: dict[str, object]
) -> None:
    with engine.begin() as conn:
        conn.execute(
            insert(audit).values(request_id=request_id, actor=actor, action=action, detail=detail)
        )
