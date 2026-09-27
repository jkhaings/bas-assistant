"""One `usage` row per model call, and the per-request receipt built from those rows."""

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Engine, insert, select

from bas_assistant.db import requests, usage
from bas_assistant.llm.gateway import Usage

Stage = Literal["router", "embed", "answer", "judge"]


def record_usage(engine: Engine, request_id: UUID | None, stage: Stage, call: Usage) -> None:
    with engine.begin() as conn:
        conn.execute(
            insert(usage).values(
                request_id=request_id,
                stage=stage,
                alias=call.alias,
                model=call.model,
                provider=call.provider,
                input_tokens=call.input_tokens,
                output_tokens=call.output_tokens,
                cached_tokens=call.cached_tokens,
                usd=call.usd,
                latency_ms=call.latency_ms,
                cache_hit=False,
            )
        )


def record_cache_hit(engine: Engine, request_id: UUID, alias: str) -> None:
    """The cache, not a model, served this request: $0 and no tokens."""
    with engine.begin() as conn:
        conn.execute(
            insert(usage).values(
                request_id=request_id,
                stage="answer",
                alias=alias,
                model="cache",
                provider="cache",
                input_tokens=0,
                output_tokens=0,
                cached_tokens=0,
                usd=Decimal(0),
                latency_ms=0,
                cache_hit=True,
            )
        )


class UsageLine(BaseModel):
    stage: str
    alias: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    usd: float
    latency_ms: int
    cache_hit: bool


class Receipt(BaseModel):
    request_id: UUID
    route: str | None
    model: str | None
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    usd: float
    retrieval_ms: int | None
    rerank_ms: int | None
    model_ms: int
    total_ms: int | None
    cache_hit: bool
    calls: list[UsageLine]


def receipt(engine: Engine, request_id: UUID) -> Receipt | None:
    with engine.connect() as conn:
        request = conn.execute(select(requests).where(requests.c.id == request_id)).first()
        rows = conn.execute(
            select(usage).where(usage.c.request_id == request_id).order_by(usage.c.created_at)
        ).all()
    if request is None:
        return None
    calls = [UsageLine.model_validate(row, from_attributes=True) for row in rows]
    answer_models = [call.model for call in calls if call.stage == "answer"]
    return Receipt(
        request_id=request_id,
        route=request.route,
        model=answer_models[-1] if answer_models else None,
        input_tokens=sum(call.input_tokens for call in calls),
        output_tokens=sum(call.output_tokens for call in calls),
        cached_tokens=sum(call.cached_tokens for call in calls),
        usd=float(sum(Decimal(row.usd) for row in rows)),
        retrieval_ms=request.retrieval_ms,
        rerank_ms=request.rerank_ms,
        model_ms=sum(call.latency_ms for call in calls),
        total_ms=request.latency_ms,
        cache_hit=any(call.cache_hit for call in calls),
        calls=calls,
    )
