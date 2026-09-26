# syntax=docker/dockerfile:1

# --- build stage ---
FROM ghcr.io/astral-sh/uv:0.11.16-python3.12-bookworm-slim AS build

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
RUN uv sync --frozen --no-dev

# --- runtime stage ---
FROM python:3.12-slim-bookworm AS runtime

# Non-root user
RUN useradd --create-home --shell /bin/bash app
USER app
WORKDIR /home/app

# Copy the installed venv and source from build stage
COPY --from=build --chown=app:app /app/.venv .venv
COPY --from=build --chown=app:app /app/src src

ENV PATH="/home/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# No ENV/ARG for secrets — read from env_file at runtime

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

CMD ["python", "-m", "bas_assistant"]
