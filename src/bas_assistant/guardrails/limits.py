"""Abuse controls on the public link: a per-IP sliding window, and one error shape for
every limit the UI has to explain (rate limit, allowance, daily cap, key budget, outage)."""

import math
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, HTTPException, Request
from redis import Redis

from bas_assistant.audit import write_audit
from bas_assistant.runtime import AppRuntime, get_runtime

LimitReason = Literal[
    "rate_limited",
    "daily_allowance_used",
    "daily_budget_reached",
    "key_budget_reached",
    "model_unavailable",
]

MESSAGES: dict[LimitReason, str] = {
    "rate_limited": "Too many questions from your network in the last minute. Try again shortly.",
    "daily_allowance_used": "This role has used today's question allowance.",
    "daily_budget_reached": "The demo has reached today's spending cap and is paused.",
    "key_budget_reached": "The demo's model budget for this period is used up.",
    "model_unavailable": (
        "The language models are unavailable right now. "
        "Your question was not counted; please try again."
    ),
}

RATE_WINDOW = timedelta(minutes=1)


def limit_detail(reason: LimitReason, resets_at: datetime | None) -> dict[str, str | None]:
    return {
        "reason": reason,
        "message": MESSAGES[reason],
        "resets_at": resets_at.isoformat() if resets_at else None,
    }


def limit_error(status: int, reason: LimitReason, resets_at: datetime | None) -> HTTPException:
    headers = None
    if resets_at is not None:
        wait = resets_at - datetime.now(UTC)
        headers = {"Retry-After": str(max(1, math.ceil(wait.total_seconds())))}
    return HTTPException(status, detail=limit_detail(reason, resets_at), headers=headers)


def attempts_in_window(redis: Redis, key: str, now: datetime) -> int:
    """Log one attempt and count the attempts in the trailing window, this one included.

    Rejected attempts are logged too, so a client that keeps hammering stays blocked.
    """
    now_s = now.timestamp()
    pipe = redis.pipeline(transaction=True)
    pipe.zremrangebyscore(key, 0, now_s - RATE_WINDOW.total_seconds())
    pipe.zadd(key, {uuid4().hex: now_s})
    pipe.zcard(key)
    pipe.expire(key, RATE_WINDOW)
    _, _, count, _ = pipe.execute()
    return int(count)


def per_ip_limit(request: Request, runtime: Annotated[AppRuntime, Depends(get_runtime)]) -> None:
    """429 once an IP sends more than the limit within a minute, whatever role it claims."""
    now = datetime.now(UTC)
    ip = request.client.host if request.client else "unknown"
    count = attempts_in_window(runtime.redis, f"ratelimit:{ip}", now)
    if count <= runtime.ip_rate_limit:
        return
    if count == runtime.ip_rate_limit + 1:
        # Once per burst, not per rejected request: the audit table is not a flood target.
        write_audit(
            runtime.agent.engine,
            None,
            actor="rate_limiter",
            action="rate_limited",
            detail={"limit": runtime.ip_rate_limit, "window_s": RATE_WINDOW.seconds},
        )
    raise limit_error(429, "rate_limited", now + RATE_WINDOW)
