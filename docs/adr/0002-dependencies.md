# ADR 0002: Runtime and dev dependencies

Running log — add a line whenever a new dependency is added to pyproject.toml.

## Runtime

| Package | Version pin | Beats in stdlib | Reason |
|---|---|---|---|
| fastapi | ≥0.115 | http.server | Async, OpenAPI, Pydantic v2 integration |
| uvicorn[standard] | ≥0.30 | — | ASGI server for FastAPI |
| pydantic | ≥2.7 | dataclasses | Validation, SecretStr, structured LLM output |
| pydantic-settings | ≥2.3 | os.environ | Reads env vars into typed Settings with masking |
| httpx | ≥0.28.1 | urllib.request | Sync HTTP client: the crawler, the embedding provider, and the LiteLLM proxy calls (`MockTransport` fakes the proxy in unit tests) |
| sqlalchemy | ≥2.0.36 | raw psycopg SQL | Typed Core statements, no hand-built SQL strings, Alembic integration |
| alembic | ≥1.14 | hand-rolled migration scripts | Versioned, reversible schema migrations |
| psycopg[binary] | ≥3.2 | — | Postgres driver; binary extra avoids a build toolchain in the image |
| pgvector | ≥0.3.6 | — | SQLAlchemy `Vector` type + HNSW index construct for the `embedding` column |
| selectolax | ≥0.3.21 | html.parser | Fast CSS-selector HTML parsing for product pages |
| docling | ≥2.15 | — | PDF parsing that preserves table structure as markdown |
| pypdfium2 | ≥4.30 | — | Already a Docling dependency (Apache-2.0); reused directly as the PDF-parse fallback instead of adding PyMuPDF (AGPL) |
| llama-index-core | ≥0.12 | — | `MarkdownNodeParser` + `SentenceSplitter` for parent-child chunking |
| sentence-transformers | ≥3.3 | — | Local `CrossEncoder` reranker (`ms-marco-MiniLM-L-6-v2` since session D, ADR 0003), no network call at query time |
| torch | ≥2.0 | — | Made a direct dependency (not left implicit via sentence-transformers): uv's `[tool.uv.sources]` platform-conditional index override only takes effect for packages also listed in `[project.dependencies]`, not purely-transitive ones — confirmed by reproduction, not documented. Without this, torch pulled the CUDA-toolkit meta-dependencies (~3 GB of nvidia-* wheels) even under the CPU-only index override. |
| langgraph | ≥1.2 | a hand-written loop | Typed state graph, `interrupt` for the human gate, checkpoint/resume (session B) |
| langgraph-checkpoint-postgres | ≥3.1 | pickle to a table | Postgres checkpointer so a paused thread survives restarts; uses the same psycopg driver (session B) |
| psycopg-pool | ≥3.3 | — | Connection pool the checkpointer requires (session B) |
| redis | ≥8.1 | functools.lru_cache | Shared answer cache and per-user allowance across workers and restarts (session B) |
| langchain-core | ≥1.6 | — | Already installed by langgraph; declared because the app imports `RunnableConfig` from it (session B) |
| prometheus-client | ≥0.26 | a hand-written text exposition | Counters, histograms and the `/metrics` text format Prometheus scrapes (session D) |
| opentelemetry-sdk | ≥1.45 | — | Spans with a batch processor; the vendor-neutral way into Langfuse, which ingests OTLP (session D) |
| opentelemetry-exporter-otlp-proto-http | ≥1.45 | urllib + hand-built protobuf | OTLP over HTTP to Langfuse (it does not accept gRPC) (session D) |
| opentelemetry-instrumentation-fastapi | ≥0.66b0 | a hand-written ASGI middleware | One root span per request with HTTP semantics, context carried into sync handlers (session D) |

## Dev / CI

| Package | Beats in stdlib | Reason |
|---|---|---|
| pytest | unittest | Fixtures, markers, parametrize |
| ruff | — | Linter + formatter, replaces flake8+isort+pyupgrade |
| mypy | — | Static type checking, strict mode |
| pre-commit | — | Git hook manager; gitleaks and ruff run pre-commit |
| fakeredis | — | Stands in for Redis in unit tests (no docker in the unit tier) (session B) |
| httpx2 | — | starlette 1.x TestClient requires it; typed test helpers (session B) |
| pyyaml + types-pyyaml | — | Test reads config/litellm.yaml to check aliases and fallback order (session B) |

## Notes

- `httpx` moved from the dev group to runtime dependencies in session A (still doubles as the
  FastAPI `TestClient` transport in tests).
- `torch` resolves to CPU-only wheels on Linux via a `[tool.uv.sources]` marker pinned to
  `pytorch-cpu`, keeping ~3 GB of CUDA wheels out of the Docker image and CI. macOS dev machines
  use the default PyPI wheel (also CPU-only there). It is listed as a direct dependency, not left
  implicit via `sentence-transformers` — see the table row above for why that's load-bearing.
