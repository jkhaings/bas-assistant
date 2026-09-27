"""Exact-match answer cache: same normalized question, role and corpus version cost $0."""

import hashlib
from datetime import timedelta

from pydantic import BaseModel
from redis import Redis

TTL = timedelta(hours=24)


def cache_key(question: str, role: str, corpus_version: str) -> str:
    normalized = " ".join(question.lower().split())
    digest = hashlib.sha256(f"{normalized}\n{role}\n{corpus_version}".encode()).hexdigest()
    return f"answer:{digest}"


def get_cached[T: BaseModel](redis: Redis, key: str, model: type[T]) -> T | None:
    raw = redis.get(key)
    return None if raw is None else model.model_validate_json(raw)


def put_cached(redis: Redis, key: str, value: BaseModel) -> None:
    redis.set(key, value.model_dump_json(), ex=TTL)
