"""FastAPI application — session 0 exposes /healthz only."""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="bas-assistant", docs_url="/docs", redoc_url=None)


class Health(BaseModel):
    """Response model for GET /healthz."""

    status: str


@app.get("/healthz", response_model=Health)
def healthz() -> Health:
    """Return ok when the app process is alive."""
    return Health(status="ok")
