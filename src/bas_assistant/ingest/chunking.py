"""Parent-child chunking: heading sections as parents, ~300-token children.

A markdown table row is never split across children — build_children uses a
custom tokenizer that treats each table row as one atomic unit (see
_line_aware_tokenizer for the separator-preserving invariant it relies on).
"""

from __future__ import annotations

import re

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from pydantic import BaseModel

PARENT_TOKEN_LIMIT = 1500
CHILD_TOKEN_LIMIT = 300
CHILD_OVERLAP = 50

_SENTENCE_END = re.compile(r"(?<=[.!?])(\s+)")


class ParentDraft(BaseModel):
    """A heading-level section, before it has a database id."""

    page_start: int
    page_end: int
    text: str


class ChildDraft(BaseModel):
    """A retrieval chunk, before it has a database id or an embedding."""

    parent_index: int
    page: int
    position: int
    text: str


def _line_aware_tokenizer(text: str) -> list[str]:
    """Split into units whose concatenation reproduces the input exactly.

    A markdown table row (a line starting with '|') is kept whole; other
    lines are split on sentence boundaries. SentenceSplitter's packer joins
    units back together by plain string concatenation, so every unit here
    must keep its own trailing whitespace — dropping it (e.g. via
    str.split("\\n")) would run table rows and sentences together with no
    separator between them.
    """
    units: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("|"):
            units.append(line)
            continue
        start = 0
        for match in _SENTENCE_END.finditer(line):
            units.append(line[start : match.end()])
            start = match.end()
        if start < len(line):
            units.append(line[start:])
    return units


def _parents_for_page(
    page_no: int,
    text: str,
    header_splitter: MarkdownNodeParser,
    section_splitter: SentenceSplitter,
) -> list[ParentDraft]:
    sections = header_splitter.get_nodes_from_documents([Document(text=text)])
    parents: list[ParentDraft] = []
    for section in sections:
        parents.extend(
            ParentDraft(page_start=page_no, page_end=page_no, text=piece)
            for piece in section_splitter.split_text(section.get_content())
        )
    return parents


def build_parents(pages: list[tuple[int, str]]) -> list[ParentDraft]:
    """Split each page into heading sections, further splitting any oversized one."""
    header_splitter = MarkdownNodeParser()
    section_splitter = SentenceSplitter(
        chunk_size=PARENT_TOKEN_LIMIT, chunk_overlap=0, paragraph_separator="\n\n"
    )
    parents: list[ParentDraft] = []
    for page_no, text in pages:
        if text.strip():
            parents.extend(_parents_for_page(page_no, text, header_splitter, section_splitter))
    return parents


def _children_for_parent(
    index: int, parent: ParentDraft, splitter: SentenceSplitter
) -> list[ChildDraft]:
    return [
        ChildDraft(parent_index=index, page=parent.page_start, position=position, text=piece)
        for position, piece in enumerate(splitter.split_text(parent.text))
    ]


def build_children(parents: list[ParentDraft]) -> list[ChildDraft]:
    """Split each parent into overlapping ~300-token children; table rows stay whole."""
    splitter = SentenceSplitter(
        chunk_size=CHILD_TOKEN_LIMIT,
        chunk_overlap=CHILD_OVERLAP,
        paragraph_separator="\n\n",
        chunking_tokenizer_fn=_line_aware_tokenizer,
    )
    children: list[ChildDraft] = []
    for index, parent in enumerate(parents):
        children.extend(_children_for_parent(index, parent, splitter))
    return children
