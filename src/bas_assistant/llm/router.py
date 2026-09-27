"""One cheap `fast` call decides whether a question needs the strong model."""

import logging
import re
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from bas_assistant.llm.gateway import Usage, complete

logger = logging.getLogger(__name__)

Route = Literal["fast", "strong"]

# The topic is echoed to the user when the graph abstains, and it never passes the answer
# validator, so only short plain words survive (no ':', '/' or '.', hence no links).
_PLAIN_TOPIC = re.compile(r"[\w ,'-]{1,60}")

ROUTER_PROMPT = (
    "Classify a staff question about building-automation products.\n"
    "simple: one fact from one document (a spec, a part number, a supported protocol).\n"
    "complex: comparing products, combining several documents, troubleshooting, or "
    "anything that needs reasoning across steps.\n"
    "topic: two to five words naming the product or subject."
)


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    complexity: Literal["simple", "complex"]
    topic: str


def classify(client: httpx.Client, question: str) -> tuple[Route, str, Usage]:
    """Return (route, topic, usage) for the question."""
    completion = complete(
        client,
        "fast",
        [{"role": "system", "content": ROUTER_PROMPT}, {"role": "user", "content": question}],
        RouteDecision,
        max_tokens=60,
    )
    try:
        decision = RouteDecision.model_validate_json(completion.content)
    except ValidationError:
        # A malformed routing answer should cost quality, not the request: use the strong model.
        logger.warning("router returned invalid output; routing to strong")
        return "strong", "", completion.usage
    route: Route = "strong" if decision.complexity == "complex" else "fast"
    topic = decision.topic if _PLAIN_TOPIC.fullmatch(decision.topic) else ""
    logger.info("routed to %s", route)
    return route, topic, completion.usage
