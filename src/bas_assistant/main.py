"""FastAPI application: /healthz, /metrics, the agent routes, the cost receipt, feedback,
search and documents, and the web app's static build at /."""

from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from functools import partial
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel

from bas_assistant.agent import api as agent_api
from bas_assistant.agent.corpus import search_corpus
from bas_assistant.api import ask, documents, evals
from bas_assistant.cost import api as cost_api
from bas_assistant.cost.budget import sync_daily_cap
from bas_assistant.feedback import api as feedback_api
from bas_assistant.observability.metrics import count_http_requests, metrics_endpoint
from bas_assistant.observability.tracing import drop_client_details, langfuse_provider
from bas_assistant.retrieval.embeddings import OpenAIEmbedder
from bas_assistant.retrieval.rerank import load_reranker
from bas_assistant.runtime import open_runtime
from bas_assistant.settings import ApiDocsSettings, Settings

Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]

# Built into the image by the Dockerfile's web stage; absent in unit tests and a bare checkout.
WEB_DIST = Path("web/dist")


class Health(BaseModel):
    """Response model for GET /healthz."""

    status: str


def healthz() -> Health:
    """Return ok when the app process is alive."""
    return Health(status="ok")


def create_app(lifespan: Lifespan, web_dist: Path = WEB_DIST, api_docs: bool = False) -> FastAPI:
    app = FastAPI(
        title="bas-assistant",
        docs_url="/docs" if api_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if api_docs else None,
        lifespan=lifespan,
    )
    app.add_api_route("/healthz", healthz, methods=["GET"], response_model=Health)
    app.add_api_route("/metrics", metrics_endpoint, methods=["GET"], include_in_schema=False)
    app.include_router(agent_api.router)
    app.include_router(cost_api.router)
    app.include_router(feedback_api.router)
    app.include_router(ask.router)
    app.include_router(documents.router)
    app.include_router(evals.router)
    app.middleware("http")(count_http_requests)
    # One root span per API request; where spans go is decided at startup (langfuse_provider).
    # The ASGI send/receive spans (one per SSE event) would bury the graph's own spans.
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="healthz,metrics",
        exclude_spans=["send", "receive"],
        server_request_hook=drop_client_details,
    )
    # Mounted last, so every API route above matches first. The UI routes by URL hash, so no
    # page path can shadow an API path; this serves index.html, /assets and /img.
    if web_dist.is_dir():
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
    return app


@asynccontextmanager
async def _serve(app: FastAPI) -> AsyncGenerator[None]:
    settings = Settings()
    # Loaded before the app reports healthy, so no request pays for loading the model.
    load_reranker(settings.rerank_model)
    tracing = langfuse_provider(settings)
    if tracing is not None:
        trace.set_tracer_provider(tracing)
    retrieve = partial(search_corpus, OpenAIEmbedder(settings), settings)
    try:
        with open_runtime(settings, retrieve) as runtime:
            sync_daily_cap(runtime.agent.engine, settings.daily_usd_cap)
            app.state.runtime = runtime
            yield
    finally:
        if tracing is not None:
            tracing.shutdown()  # flushes spans still in the batch


app = create_app(_serve, api_docs=ApiDocsSettings().api_docs)
