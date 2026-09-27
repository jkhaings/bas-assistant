"""Agent-graph test doubles for every tier: a LiteLLM proxy stand-in at the HTTP boundary,
a fixed retriever, and an app client wired to a given runtime. (tests/fakes.py holds the
retrieval pipeline's fakes.)

The app's gateway code runs for real against the fake proxy; only the network hop is
replaced. Passages are synthetic and describe no real product.
"""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import httpx
import httpx2
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bas_assistant.agent.state import Passage, Retrieval
from bas_assistant.llm.gateway import Usage
from bas_assistant.main import create_app
from bas_assistant.runtime import AppRuntime

ADMIN_TOKEN = "unit-test-admin-token"

DEPLOYMENTS = {
    "fast": "openai/gpt-4o-mini",
    "strong": "anthropic/claude-sonnet-4-6",
    "embed": "openai/text-embedding-3-small",
}
COST_USD = {"fast": "0.0001", "strong": "0.003", "embed": "0.00001"}
INPUT_TOKENS = 100
OUTPUT_TOKENS = 20

SOURCE_URL = "https://docs.example.com/sample-controller.pdf"
# Chunk ids are UUIDs in the real corpus, and request_chunks stores them as such.
CHUNK_1 = "00000000-0000-4000-8000-000000000001"
CHUNK_2 = "00000000-0000-4000-8000-000000000002"
PASSAGES = [
    Passage(
        chunk_id=CHUNK_1,
        document_title="Sample Controller Catalog Sheet",
        page=2,
        source_url=SOURCE_URL,
        text="The sample controller draws 4 W at 24 VAC.",
        score=0.92,
    ),
    Passage(
        chunk_id=CHUNK_2,
        document_title="Sample Controller Catalog Sheet",
        page=3,
        source_url=SOURCE_URL,
        text="Replacement parts for the sample controller are ordered through support.",
        score=0.81,
    ),
]


def answer_json(
    answer: str = "The sample controller draws 4 W at 24 VAC.",
    citations: tuple[str, ...] = (CHUNK_1,),
    ticket_title: str | None = None,
    answerable: bool = True,
) -> str:
    draft = (
        {"title": ticket_title, "body": "Customer needs a replacement."} if ticket_title else None
    )
    return json.dumps(
        {
            "answerable": answerable,
            "answer": answer,
            "citations": list(citations),
            "confidence": "high",
            "needs_ticket": draft is not None,
            "ticket_draft": draft,
        }
    )


@dataclass
class FakeProxy:
    complexity: str = "simple"
    # Raw router output to send instead of a well-formed RouteDecision.
    route_reply: str | None = None
    answers: list[str] = field(default_factory=list)
    down: set[str] = field(default_factory=set)
    # Request bodies as the app sent them (decoded JSON).
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        alias = body["model"]
        self.calls.append(body)
        if alias in self.down:
            return httpx.Response(503, json={"error": {"message": f"{alias} unavailable"}})
        headers = {
            "x-litellm-model-id": DEPLOYMENTS[alias],
            "x-litellm-response-cost": COST_USD[alias],
        }
        usage = {"prompt_tokens": INPUT_TOKENS, "completion_tokens": OUTPUT_TOKENS}
        if request.url.path == "/v1/embeddings":
            data = [{"index": i, "embedding": [float(i)] * 3} for i in range(len(body["input"]))]
            return httpx.Response(200, json={"data": data, "usage": usage}, headers=headers)
        content = self._reply(body["response_format"]["json_schema"]["name"])
        choice = {"message": {"role": "assistant", "content": content}}
        return httpx.Response(200, json={"choices": [choice], "usage": usage}, headers=headers)

    def _reply(self, schema_name: str) -> str:
        if schema_name == "RouteDecision":
            topic_json = json.dumps({"complexity": self.complexity, "topic": "controller power"})
            return self.route_reply if self.route_reply is not None else topic_json
        return self.answers.pop(0) if self.answers else answer_json()

    def answer_calls(self) -> list[dict[str, Any]]:
        """Request bodies (decoded JSON) of the answer calls."""
        return [
            call
            for call in self.calls
            if call["response_format"]["json_schema"]["name"] == "AnswerOut"
        ]


@dataclass
class FakeRetriever:
    passages: list[Passage] = field(default_factory=lambda: list(PASSAGES))
    embed: Usage | None = None
    seen_acl_groups: list[list[str]] = field(default_factory=list)

    def __call__(self, _question: str, acl_groups: list[str]) -> Retrieval:
        self.seen_acl_groups.append(acl_groups)
        return Retrieval(passages=self.passages, retrieval_ms=12, rerank_ms=34, embed=self.embed)


@asynccontextmanager
async def _no_startup(_app: FastAPI) -> AsyncGenerator[None]:
    yield


def make_client(runtime: AppRuntime) -> TestClient:
    app = create_app(_no_startup)
    app.state.runtime = runtime
    return TestClient(app)


def ask(
    client: TestClient, question: str, role: str = "support", thread_id: str | None = None
) -> httpx2.Response:
    body: dict[str, str] = {"question": question}
    if thread_id:
        body["thread_id"] = thread_id
    return client.post("/ask", json=body, headers={"X-Demo-Role": role})
