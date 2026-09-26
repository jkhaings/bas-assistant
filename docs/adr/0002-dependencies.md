# ADR 0002: Runtime and dev dependencies

Running log — add a line whenever a new dependency is added to pyproject.toml.

## Runtime

| Package | Version pin | Beats in stdlib | Reason |
|---|---|---|---|
| fastapi | ≥0.115 | http.server | Async, OpenAPI, Pydantic v2 integration |
| uvicorn[standard] | ≥0.30 | — | ASGI server for FastAPI |
| pydantic | ≥2.7 | dataclasses | Validation, SecretStr, structured LLM output |
| pydantic-settings | ≥2.3 | os.environ | Reads env vars into typed Settings with masking |

## Dev / CI

| Package | Beats in stdlib | Reason |
|---|---|---|
| pytest | unittest | Fixtures, markers, parametrize |
| httpx | urllib | Async TestClient for FastAPI |
| ruff | — | Linter + formatter, replaces flake8+isort+pyupgrade |
| mypy | — | Static type checking, strict mode |
| pre-commit | — | Git hook manager; gitleaks and ruff run pre-commit |
