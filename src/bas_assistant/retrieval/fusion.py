"""Reciprocal rank fusion: combine two ranked chunk-id lists into one ranking."""

from __future__ import annotations

import uuid


def rrf(
    vec_ranks: dict[uuid.UUID, int], lex_ranks: dict[uuid.UUID, int], k: int = 60
) -> dict[uuid.UUID, float]:
    """Return an RRF score per chunk id, higher is better.

    Each rank dict maps a chunk id to its 1-based position in that ranking; a
    chunk missing from one ranking contributes nothing from it.
    """
    scores: dict[uuid.UUID, float] = {}
    for ranks in (vec_ranks, lex_ranks):
        for chunk_id, rank in ranks.items():
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return scores
