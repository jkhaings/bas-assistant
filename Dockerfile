# syntax=docker/dockerfile:1

# --- build stage ---
FROM ghcr.io/astral-sh/uv:0.11.16-python3.12-trixie-slim AS build

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
# Non-editable so the venv does not point back into the build stage's source tree.
RUN uv sync --frozen --no-dev --no-editable

# --- runtime stage ---
FROM python:3.12-slim-trixie AS runtime

# Non-root user
RUN useradd --create-home --shell /bin/bash app
WORKDIR /app
RUN chown app:app /app
USER app

# Same /app/.venv path as the build stage: console scripts (alembic) keep valid shebangs.
COPY --from=build --chown=app:app /app/.venv .venv
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic/ alembic/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# No ENV/ARG for secrets — read from env_file at runtime

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

CMD ["python", "-m", "bas_assistant"]
