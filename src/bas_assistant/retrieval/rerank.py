"""Local cross-encoder reranker: BAAI/bge-reranker-base, loaded once per model name.

No network call at query time — the model is cached in the model_cache volume
after its first download.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from typing import cast

from sentence_transformers import CrossEncoder

Reranker = Callable[[str, list[str]], list[float]]


@cache
def _model(model_name: str) -> CrossEncoder:
    # sentence_transformers ships no type stubs, so its constructor resolves
    # to Any; cast to the real return type instead of leaking Any outward.
    return cast(CrossEncoder, CrossEncoder(model_name))


def rerank(model_name: str, query: str, passages: list[str]) -> list[float]:
    """Score each passage against the query with `model_name`; higher is more relevant."""
    model = _model(model_name)
    scores = model.predict([(query, passage) for passage in passages])
    return [float(score) for score in scores]
