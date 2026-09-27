"""One cheap `fast` call routes the question and flags injection or off-topic requests."""

import logging
import re
from dataclasses import dataclass
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from bas_assistant.agent.prompts import ROUTER_PROMPT
from bas_assistant.llm.gateway import Usage, complete

logger = logging.getLogger(__name__)

Route = Literal["fast", "strong"]
RefusalKind = Literal["injection", "off_topic"]
# "unclear" is a question the company could be asked that the documents may not cover
# (a refund, an account): it goes to retrieval and abstains there, never to a refusal.
Scope = Literal["on_topic", "unclear", "off_topic"]

# Room for the flags and a one-sentence reason next to the route and topic.
ROUTER_MAX_TOKENS = 120

# The topic is echoed to the user when the graph abstains, and it never passes the answer
# validator, so only short plain words survive (no ':', '/' or '.', hence no links).
_PLAIN_TOPIC = re.compile(r"[\w ,'-]{1,60}")


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    complexity: Literal["simple", "complex"]
    topic: str
    is_injection: bool
    scope: Scope
    reason: str


@dataclass(frozen=True)
class Classification:
    route: Route
    topic: str
    # Set when the question must be refused; the reason is audited, never shown.
    refusal: RefusalKind | None
    reason: str
    usage: Usage


def _refusal(decision: RouteDecision) -> RefusalKind | None:
    # The model also ticks is_injection for plain unrelated requests ("write me a poem" reads
    # as another task), and the injection message would be the wrong one to show. Real
    # override phrasings are caught by the pattern rail before this call.
    if decision.scope == "off_topic":
        return "off_topic"
    return "injection" if decision.is_injection else None


def classify(client: httpx.Client, question: str) -> Classification:
    completion = complete(
        client,
        "fast",
        [{"role": "system", "content": ROUTER_PROMPT}, {"role": "user", "content": question}],
        RouteDecision,
        max_tokens=ROUTER_MAX_TOKENS,
    )
    try:
        decision = RouteDecision.model_validate_json(completion.content)
    except ValidationError:
        # A malformed routing answer should cost quality, not the request: use the strong
        # model. The pattern rail has already run, and the output fence still applies.
        logger.warning("router returned invalid output; routing to strong")
        return Classification("strong", "", None, "", completion.usage)
    route: Route = "strong" if decision.complexity == "complex" else "fast"
    topic = decision.topic if _PLAIN_TOPIC.fullmatch(decision.topic) else ""
    logger.info("routed to %s", route)
    return Classification(route, topic, _refusal(decision), decision.reason, completion.usage)
