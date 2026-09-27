"""Append-only audit rows. Never store raw questions or PII in detail."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Engine, insert

from bas_assistant.db.activity import Audit


def write_audit(
    engine: Engine, request_id: UUID | None, actor: str, action: str, detail: dict[str, object]
) -> None:
    with engine.begin() as conn:
        conn.execute(
            insert(Audit).values(
                request_id=request_id,
                actor=actor,
                action=action,
                detail=detail,
                # Explicit so rows written within one second keep their order everywhere.
                created_at=datetime.now(UTC),
            )
        )
