"""Code checks on a model answer before anyone sees it. No model call."""

import re

from bas_assistant.agent.state import AnswerOut, Passage

# Anything a markdown renderer or a reader could follow: bare URLs in any case, www.
# domains, inline link targets (including //host and javascript:), reference definitions
# ("[1]: url"), <scheme:...> autolinks and HTML href/src attributes.
_LINK_PATTERNS = (
    re.compile(r"(?:https?://|www\.)[^\s<>()\[\]\"'`]+", re.IGNORECASE),
    re.compile(r"\]\(\s*<?([^)\s>]+)"),
    re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?([^\s>]+)", re.MULTILINE),
    re.compile(r"<([a-z][a-z0-9+.-]*:[^>\s]+)>", re.IGNORECASE),
    re.compile(r"\b(?:href|src)\s*=\s*[\"']?([^\"'\s>]+)", re.IGNORECASE),
)
# Any markdown image opener, inline or reference-style, and HTML images.
_IMAGE = re.compile(r"!\[|<img\b", re.IGNORECASE)


def _link_violations(text: str, source_urls: set[str]) -> list[str]:
    links = [link for pattern in _LINK_PATTERNS for link in pattern.findall(text)]
    return [
        f"link {link!r} is not the source url of a provided passage"
        for link in dict.fromkeys(link.rstrip(".,;:") for link in links)
        if link not in source_urls
    ]


def find_violations(draft: AnswerOut, passages: list[Passage]) -> list[str]:
    """Every reason the answer must not be shown; empty means it passes."""
    passage_ids = {passage.chunk_id for passage in passages}
    source_urls = {passage.source_url for passage in passages}
    ticket = draft.ticket_draft
    shown_text = draft.answer + (f"\n{ticket.title}\n{ticket.body}" if ticket else "")
    violations = [
        f"citation {cited!r} is not one of the provided passage ids"
        for cited in draft.citations
        if cited not in passage_ids
    ]
    if draft.answerable and not draft.citations:
        violations.append("the answer cites no passage")
    violations += _link_violations(shown_text, source_urls)
    if _IMAGE.search(shown_text):
        violations.append("the answer contains an image")
    if draft.needs_ticket and ticket is None:
        violations.append("needs_ticket is true but ticket_draft is null")
    return violations
