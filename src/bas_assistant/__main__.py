"""Entry point: configure logging then start uvicorn."""

import uvicorn

from bas_assistant.logging import configure_logging

configure_logging()

if __name__ == "__main__":  # pragma: no cover
    uvicorn.run(
        "bas_assistant.main:app",
        host="0.0.0.0",
        port=8000,
        log_config=None,  # use our JSON handler, not uvicorn's
    )
