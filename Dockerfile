# syntax=docker/dockerfile:1

# --- web stage: the React build FastAPI serves at / ---
# node 24-slim, pinned by digest like the LiteLLM image (multi-arch index: the droplet is x86_64).
FROM node:24-slim@sha256:0e0ff40c39bc087845bfb27465a0df4ea419520094bc35842ff83dd8cbe6f9b6 AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY web/ ./
RUN npm run build

# --- build stage ---
# astral-sh only publishes the combined <uv-version>-python<py>-<os> tag up to
# uv 0.9.x; from 0.10 on, the documented pattern is to copy the uv binary
# (still tagged per-version) onto a plain Python base instead.
FROM python:3.12-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /usr/local/bin/

# Generous timeout for large ML wheels (torch et al.) on a slow or flaky link. Bytecode compiled
# at build time: without .pyc files a cold start spent 4 minutes importing torch and transformers
# on a loaded host (HANDOFF_D.md), and the app is unhealthy until those imports finish.
ENV UV_HTTP_TIMEOUT=180 \
    UV_COMPILE_BYTECODE=1

WORKDIR /app
COPY pyproject.toml uv.lock ./
# Cache mount: uv's downloaded wheels survive a failed layer and retried
# builds, instead of re-fetching several hundred MB from scratch each time.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --no-editable

COPY src/ src/
COPY alembic.ini README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# --- runtime stage ---
FROM python:3.12-slim-bookworm AS runtime

# opencv (a docling/easyocr dependency) needs libGL and glib at import time.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash app
WORKDIR /app
# Pre-create the model_cache mount point with the right owner: an anonymous
# path that doesn't exist yet in the image is created root-owned the first
# time a named volume mounts over it, which the non-root `app` user can't
# write into.
RUN mkdir -p /app/.cache/huggingface && chown -R app:app /app
USER app

# Same /app path as the build stage: alembic.ini's `prepend_sys_path = src`
# resolves relative to this directory.
COPY --from=build --chown=app:app /app/.venv .venv
COPY --from=build --chown=app:app /app/src src
COPY --from=build --chown=app:app /app/alembic.ini ./
COPY --from=web --chown=app:app /web/dist web/dist

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/app/.cache/huggingface \
    HF_HUB_DISABLE_XET=1

# No ENV/ARG for secrets — read from env_file at runtime

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

CMD ["python", "-m", "bas_assistant"]
