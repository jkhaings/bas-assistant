"""Prompts, versioned: invariants in the system message, passages wrapped as data.

The prompt texts are the .md files next to this module. PROMPT_VERSION is a hash of all of
them, so any edit changes it; requests and eval runs record it.
"""

from __future__ import annotations

import hashlib
from importlib.resources import files
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape, quoteattr

if TYPE_CHECKING:
    # Type-only: llm/router imports this package, and agent.state imports llm/router.
    from bas_assistant.agent.state import AgentState, Passage

HISTORY_TURNS = 6

_PROMPT_FILES = ("answer_system.md", "ticket_rule.md", "no_ticket_rule.md", "router.md")
_TEXTS = {name: files(__name__).joinpath(name).read_text().strip() for name in _PROMPT_FILES}

SYSTEM_PROMPT = _TEXTS["answer_system.md"]
TICKET_RULE = _TEXTS["ticket_rule.md"]
NO_TICKET_RULE = _TEXTS["no_ticket_rule.md"]
ROUTER_PROMPT = _TEXTS["router.md"]

PROMPT_VERSION = hashlib.sha256(
    "\n\n".join(_TEXTS[name] for name in _PROMPT_FILES).encode()
).hexdigest()[:12]


def system_prompt(tools_allowed: list[str]) -> str:
    # A role that cannot create tickets never hears about them.
    rule = TICKET_RULE if "create_ticket" in tools_allowed else NO_TICKET_RULE
    return f"{SYSTEM_PROMPT}\n{rule}"


def render_passages(passages: list[Passage]) -> str:
    return "\n".join(
        f"<passage id={quoteattr(p.chunk_id)} document={quoteattr(p.document_title)} "
        f"page={quoteattr(str(p.page))} source_url={quoteattr(p.source_url)}>\n"
        f"{escape(p.text)}\n</passage>"
        for p in passages
    )


def build_messages(state: AgentState) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": system_prompt(state.user.tools_allowed)}]
    for turn in state.history[-HISTORY_TURNS:]:
        messages.append({"role": "user", "content": turn.question})
        messages.append({"role": "assistant", "content": turn.answer})
    request = f"{render_passages(state.retrieved)}\n\nQuestion: {state.question}"
    if state.validation_errors:
        problems = "\n".join(f"- {error}" for error in state.validation_errors)
        request += f"\n\nYour previous answer was rejected. Fix these problems:\n{problems}"
    messages.append({"role": "user", "content": request})
    return messages
