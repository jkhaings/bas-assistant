"""GET /requests/{id}/receipt: what one answer cost and where the time went. GET /budget: today's
spend against the global daily cap, for the UI's budget chip."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from bas_assistant.cost.budget import next_reset, spent_today
from bas_assistant.cost.usage import Receipt, receipt
from bas_assistant.runtime import AppRuntime, get_runtime

router = APIRouter()


class BudgetOut(BaseModel):
    spent_usd: float
    cap_usd: float
    resets_at: datetime


@router.get("/requests/{request_id}/receipt")
def get_receipt(request_id: UUID, runtime: Annotated[AppRuntime, Depends(get_runtime)]) -> Receipt:
    found = receipt(runtime.agent.engine, request_id)
    if found is None:
        raise HTTPException(404, detail="request not found")
    return found


@router.get("/budget")
def get_budget(runtime: Annotated[AppRuntime, Depends(get_runtime)]) -> BudgetOut:
    now = datetime.now(UTC)
    return BudgetOut(
        spent_usd=float(spent_today(runtime.agent.engine, now)),
        cap_usd=float(runtime.daily_usd_cap),
        resets_at=next_reset(now),
    )
