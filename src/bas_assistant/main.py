"""FastAPI application: /healthz, the agent routes and the cost receipt."""

from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from bas_assistant.agent import api as agent_api
from bas_assistant.agent.state import Retrieval
from bas_assistant.cost import api as cost_api
from bas_assistant.runtime import open_runtime
from bas_assistant.settings import Settings

Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


class Health(BaseModel):
    """Response model for GET /healthz."""

    status: str


def healthz() -> Health:
    """Return ok when the app process is alive."""
    return Health(status="ok")


def create_app(lifespan: Lifespan) -> FastAPI:
    app = FastAPI(title="bas-assistant", docs_url="/docs", redoc_url=None, lifespan=lifespan)
    app.add_api_route("/healthz", healthz, methods=["GET"], response_model=Health)
    app.include_router(agent_api.router)
    app.include_router(cost_api.router)
    return app


# TODO(session A merge): replace with the VectorStore search adapted to return Retrieval.
def no_corpus_yet(_question: str, _acl_groups: list[str]) -> Retrieval:
    """Session A's VectorStore replaces this at merge; until then every question abstains."""
    return Retrieval(passages=[], retrieval_ms=0, rerank_ms=0)


@asynccontextmanager
async def _serve(app: FastAPI) -> AsyncGenerator[None]:
    with open_runtime(Settings(), no_corpus_yet) as runtime:
        app.state.runtime = runtime
        yield


app = create_app(_serve)
