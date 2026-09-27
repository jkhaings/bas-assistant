"""FastAPI application: health check, retrieval, and document listing."""

from fastapi import FastAPI
from pydantic import BaseModel

from bas_assistant.api import ask, documents

app = FastAPI(title="bas-assistant", docs_url="/docs", redoc_url=None)
app.include_router(ask.router)
app.include_router(documents.router)


class Health(BaseModel):
    """Response model for GET /healthz."""

    status: str


@app.get("/healthz", response_model=Health)
def healthz() -> Health:
    """Return ok when the app process is alive."""
    return Health(status="ok")
