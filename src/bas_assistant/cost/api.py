"""GET /requests/{id}/receipt: what one answer cost and where the time went."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from bas_assistant.cost.usage import Receipt, receipt
from bas_assistant.runtime import AppRuntime, get_runtime

router = APIRouter()


@router.get("/requests/{request_id}/receipt")
def get_receipt(request_id: UUID, runtime: Annotated[AppRuntime, Depends(get_runtime)]) -> Receipt:
    found = receipt(runtime.agent.engine, request_id)
    if found is None:
        raise HTTPException(404, detail="request not found")
    return found
