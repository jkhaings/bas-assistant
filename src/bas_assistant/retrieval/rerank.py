"""Local cross-encoder reranker (settings.rerank_model), loaded once at app startup.

No network call at query time — the model is cached in the model_cache volume
after its first download.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from typing import cast

from sentence_transformers import CrossEncoder
from torch import nn

Reranker = Callable[[str, list[str]], list[float]]


@cache
def load_reranker(model_name: str) -> CrossEncoder:
    """The model, loaded on first use and kept in memory; the app calls this at startup."""
    # Sigmoid explicitly: some cross-encoders ship an identity activation (raw logits),
    # and rerank_threshold assumes scores in 0-1 whichever model is configured.
    # sentence_transformers' constructor resolves to Any; cast to the real type.
    return cast(CrossEncoder, CrossEncoder(model_name, activation_fn=nn.Sigmoid()))


def rerank(model_name: str, query: str, passages: list[str]) -> list[float]:
    """Score each passage against the query with `model_name`; higher is more relevant."""
    model = load_reranker(model_name)
    scores = model.predict([(query, passage) for passage in passages], show_progress_bar=False)
    return [float(score) for score in scores]
