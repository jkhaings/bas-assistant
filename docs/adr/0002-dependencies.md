# ADR 0002: Runtime and dev dependencies

Running log — add a line whenever a new dependency is added to pyproject.toml.

## Runtime

| Package | Version pin | Beats in stdlib | Reason |
|---|---|---|---|
| fastapi | ≥0.115 | http.server | Async, OpenAPI, Pydantic v2 integration |
| uvicorn[standard] | ≥0.30 | — | ASGI server for FastAPI |
| pydantic | ≥2.7 | dataclasses | Validation, SecretStr, structured LLM output |
| pydantic-settings | ≥2.3 | os.environ | Reads env vars into typed Settings with masking |
| langgraph | ≥1.2 | a hand-written loop | Typed state graph, `interrupt` for the human gate, checkpoint/resume (session B) |
| langgraph-checkpoint-postgres | ≥3.1 | pickle to a table | Postgres checkpointer so a paused thread survives restarts (session B) |
| psycopg[binary] + psycopg-pool | ≥3.3 | — | Postgres driver for SQLAlchemy and the checkpointer; one driver for both (session B) |
| sqlalchemy | ≥2.1 | sqlite3 / string SQL | Core tables and queries, portable to SQLite for unit tests (session B) |
| alembic | ≥1.20 | hand-run SQL files | Versioned migrations from the same table definitions (session B) |
| redis | ≥8.1 | functools.lru_cache | Shared answer cache and per-user allowance across workers and restarts (session B) |
| httpx | ≥0.28 | urllib.request | Calls the LiteLLM proxy; `MockTransport` gives unit tests a fake proxy at the HTTP boundary (session B) |
| langchain-core | ≥1.6 | — | Already installed by langgraph; declared because the app imports `RunnableConfig` from it (session B) |

## Dev / CI

| Package | Beats in stdlib | Reason |
|---|---|---|
| pytest | unittest | Fixtures, markers, parametrize |
| httpx | urllib | Async TestClient for FastAPI |
| ruff | — | Linter + formatter, replaces flake8+isort+pyupgrade |
| mypy | — | Static type checking, strict mode |
| pre-commit | — | Git hook manager; gitleaks and ruff run pre-commit |
| fakeredis | — | Stands in for Redis in unit tests (no docker in the unit tier) (session B) |
| httpx2 | — | starlette 1.x TestClient requires it; typed test helpers (session B) |
| pyyaml + types-pyyaml | — | Test reads config/litellm.yaml to check aliases and fallback order (session B) |
