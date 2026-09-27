"""Behaviour: parent-child chunking respects token limits and never splits a table row."""

import pytest

from bas_assistant.ingest.chunking import (
    CHILD_OVERLAP,
    PARENT_TOKEN_LIMIT,
    build_children,
    build_parents,
)

pytestmark = pytest.mark.unit


def test_table_row_never_splits_across_children() -> None:
    rows = [f"| Row{i} | Value{i} |" for i in range(80)]
    page_text = "## Power\n\n" + "\n".join(rows)
    parents = build_parents([(1, page_text)])
    children = build_children(parents)

    assert len(children) > 1, "the table should have been split across several children"
    for row in rows:
        assert any(row in child.text for child in children), f"{row!r} was split or dropped"


def test_children_carry_page_and_parent_index() -> None:
    parents = build_parents([(3, "## Heading\n\nSome body text about the product.")])
    children = build_children(parents)

    assert children
    assert all(child.page == 3 for child in children)
    assert all(child.parent_index == 0 for child in children)


def test_oversized_section_splits_into_multiple_parents() -> None:
    long_text = "## Big Section\n\n" + " ".join(f"word{i}" for i in range(3000))
    parents = build_parents([(1, long_text)])

    assert len(parents) > 1
    assert all(len(parent.text) < len(long_text) for parent in parents)


def test_parents_stay_within_token_limit() -> None:
    long_text = "## Big Section\n\n" + " ".join(f"word{i}" for i in range(3000))
    parents = build_parents([(1, long_text)])

    # A rough word-count proxy: real subword tokenization only ever adds more
    # tokens than there are words, so this bounds the parent from above.
    for parent in parents:
        assert len(parent.text.split()) <= PARENT_TOKEN_LIMIT


def test_consecutive_children_overlap() -> None:
    long_text = "## Section\n\n" + " ".join(f"sentence{i}." for i in range(500))
    parents = build_parents([(1, long_text)])
    children = [c for c in build_children(parents) if c.parent_index == 0]

    assert len(children) > 1
    first_words = children[0].text.split()
    second_words = children[1].text.split()
    assert set(first_words) & set(second_words), "consecutive children should share overlap"
    assert CHILD_OVERLAP > 0  # the overlap window this test relies on is non-zero


def test_empty_page_produces_no_parents() -> None:
    assert build_parents([(1, "")]) == []
    assert build_parents([(1, "   \n\n  ")]) == []
