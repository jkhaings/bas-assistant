"""Global daily USD cap (summed from `usage`) and per-user daily question allowance (Redis)."""

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from redis import Redis
from sqlalchemy import Engine, func, select

from bas_assistant.db.activity import Usage


def next_reset(now: datetime) -> datetime:
    """Both limits reset at midnight UTC."""
    return datetime.combine(now.date() + timedelta(days=1), time(), tzinfo=UTC)


def spent_today(engine: Engine, now: datetime) -> Decimal:
    midnight = datetime.combine(now.date(), time(), tzinfo=UTC)
    with engine.connect() as conn:
        total: Decimal = conn.execute(
            select(func.coalesce(func.sum(Usage.usd), 0)).where(Usage.created_at >= midnight)
        ).scalar_one()
    return Decimal(total)


def _allowance_key(user_id: UUID, now: datetime) -> str:
    return f"allowance:{user_id}:{now.date().isoformat()}"


def take_allowance(redis: Redis, user_id: UUID, limit: int, now: datetime) -> bool:
    """Count one question against today's allowance; False (and uncounted) when over."""
    key = _allowance_key(user_id, now)
    used = int(redis.incr(key))
    redis.expire(key, timedelta(days=2))
    if used <= limit:
        return True
    redis.decr(key)
    return False


def refund_allowance(redis: Redis, user_id: UUID, now: datetime) -> None:
    """Server-side failures do not cost the user a question."""
    redis.decr(_allowance_key(user_id, now))
