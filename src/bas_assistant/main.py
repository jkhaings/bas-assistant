"""FastAPI application: /healthz, the agent routes, the cost receipt, search and documents."""

from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from functools import partial

from fastapi import FastAPI
from pydantic import BaseModel

from bas_assistant.agent import api as agent_api
from bas_assistant.agent.corpus import search_corpus
from bas_assistant.api import ask, documents
from bas_assistant.cost import api as cost_api
from bas_assistant.retrieval.embeddings import OpenAIEmbedder
from bas_assistant.retrieval.rerank import load_reranker
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
    app.include_router(ask.router)
    app.include_router(documents.router)
    return app


@asynccontextmanager
async def _serve(app: FastAPI) -> AsyncGenerator[None]:
    settings = Settings()
    # Loaded before the app reports healthy, so no request pays for loading the model.
    load_reranker(settings.rerank_model)
    retrieve = partial(search_corpus, OpenAIEmbedder(settings), settings)
    with open_runtime(settings, retrieve) as runtime:
        app.state.runtime = runtime
        yield


app = create_app(_serve)
