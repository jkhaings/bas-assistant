# ADR 0002: Runtime and dev dependencies

Running log — add a line whenever a new dependency is added to pyproject.toml.

## Runtime

| Package | Version pin | Beats in stdlib | Reason |
|---|---|---|---|
| fastapi | ≥0.115 | http.server | Async, OpenAPI, Pydantic v2 integration |
| uvicorn[standard] | ≥0.30 | — | ASGI server for FastAPI |
| pydantic | ≥2.7 | dataclasses | Validation, SecretStr, structured LLM output |
| pydantic-settings | ≥2.3 | os.environ | Reads env vars into typed Settings with masking |
| httpx | ≥0.28.1 | urllib.request | Sync HTTP client; used by the crawler and the embedding provider |
| sqlalchemy | ≥2.0.36 | raw psycopg SQL | Typed Core statements, no hand-built SQL strings, Alembic integration |
| alembic | ≥1.14 | hand-rolled migration scripts | Versioned, reversible schema migrations |
| psycopg[binary] | ≥3.2 | — | Postgres driver; binary extra avoids a build toolchain in the image |
| pgvector | ≥0.3.6 | — | SQLAlchemy `Vector` type + HNSW index construct for the `embedding` column |
| selectolax | ≥0.3.21 | html.parser | Fast CSS-selector HTML parsing for product pages |
| docling | ≥2.15 | — | PDF parsing that preserves table structure as markdown |
| pypdfium2 | ≥4.30 | — | Already a Docling dependency (Apache-2.0); reused directly as the PDF-parse fallback instead of adding PyMuPDF (AGPL) |
| llama-index-core | ≥0.12 | — | `MarkdownNodeParser` + `SentenceSplitter` for parent-child chunking |
| sentence-transformers | ≥3.3 | — | Local `CrossEncoder` reranker (`bge-reranker-base`), no network call at query time |
| torch | ≥2.0 | — | Made a direct dependency (not left implicit via sentence-transformers): uv's `[tool.uv.sources]` platform-conditional index override only takes effect for packages also listed in `[project.dependencies]`, not purely-transitive ones — confirmed by reproduction, not documented. Without this, torch pulled the CUDA-toolkit meta-dependencies (~3 GB of nvidia-* wheels) even under the CPU-only index override. |

## Dev / CI

| Package | Beats in stdlib | Reason |
|---|---|---|
| pytest | unittest | Fixtures, markers, parametrize |
| ruff | — | Linter + formatter, replaces flake8+isort+pyupgrade |
| mypy | — | Static type checking, strict mode |
| pre-commit | — | Git hook manager; gitleaks and ruff run pre-commit |

## Notes

- `httpx` moved from the dev group to runtime dependencies in session A (still doubles as the
  FastAPI `TestClient` transport in tests).
- `torch` resolves to CPU-only wheels on Linux via a `[tool.uv.sources]` marker pinned to
  `pytorch-cpu`, keeping ~3 GB of CUDA wheels out of the Docker image and CI. macOS dev machines
  use the default PyPI wheel (also CPU-only there). It is listed as a direct dependency, not left
  implicit via `sentence-transformers` — see the table row above for why that's load-bearing.
