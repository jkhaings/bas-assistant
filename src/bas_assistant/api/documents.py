"""GET /documents: the corpus visible to the caller's role."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from bas_assistant.api.roles import Role, acl_groups_for_role, demo_role
from bas_assistant.db.corpus import Document
from bas_assistant.db.engine import get_session

router = APIRouter()


class DocumentSummary(BaseModel):
    """One row of GET /documents."""

    id: uuid.UUID
    title: str
    source_url: str
    product: str
    doc_type: str


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents(
    role: Role = Depends(demo_role), session: Session = Depends(get_session)
) -> list[DocumentSummary]:
    """List ingested documents visible to this role, ACL-filtered."""
    acl_groups = acl_groups_for_role(role)
    stmt = select(Document).where(Document.acl_groups.op("&&")(acl_groups)).order_by(Document.title)
    documents = session.scalars(stmt).all()
    return [
        DocumentSummary(
            id=d.id, title=d.title, source_url=d.source_url, product=d.product, doc_type=d.doc_type
        )
        for d in documents
    ]
