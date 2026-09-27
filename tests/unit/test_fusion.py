"""Behaviour: reciprocal rank fusion combines two rankings into one score per id."""

import uuid

import pytest

from bas_assistant.retrieval.fusion import rrf

pytestmark = pytest.mark.unit


def test_id_ranked_first_in_both_lists_scores_highest() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    scores = rrf({a: 1, b: 2, c: 3}, {a: 1, b: 3, c: 2})

    assert scores[a] == max(scores.values())


def test_id_in_only_one_ranking_still_scores() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    scores = rrf({a: 1}, {b: 1})

    assert a in scores
    assert b in scores
    assert scores[a] == scores[b]  # both are rank 1 in their own list


def test_score_matches_the_rrf_formula() -> None:
    a = uuid.uuid4()
    scores = rrf({a: 5}, {}, k=60)

    assert scores[a] == pytest.approx(1.0 / (60 + 5))


def test_empty_rankings_produce_no_scores() -> None:
    assert rrf({}, {}) == {}
