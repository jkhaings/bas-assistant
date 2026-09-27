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
| presidio-analyzer | ≥2.2.364 | `re` for emails only | Entity-aware PII detection (names, phones, locations, emails) on the question before storage or any model, and on the answer (session C) |
| presidio-anonymizer | ≥2.2.364 | string slicing | Replaces detected spans with `<ENTITY_TYPE>` and resolves overlaps (session C) |
| en-core-web-sm | 3.8.0 (wheel URL) | — | The spaCy model Presidio's name and place recognizer needs. `sm` is 12 MB against `lg`'s ~560 MB, so CI and the image stay small. It never tags street lines, so a Presidio `PatternRecognizer` covers those. Not on PyPI, so pinned by release URL (session C) |
| tenacity | ≥9.1 | a hand-written sleep loop | Already in the lockfile (langchain-core). Retry with exponential backoff on the crawler's transient network and 5xx errors (session C) |
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
| ragas | — | RAGAS faithfulness, answer relevancy, context precision and recall over the golden answers (`eval/ragas_run.py`, `make eval`); dev only, never in the image (session C) |
| langchain-openai | — | The OpenAI-compatible client RAGAS judges through. It is pointed at the LiteLLM proxy's `fast` and `embed` aliases with the app's virtual key, so no vendor endpoint or vendor key is involved. An httpx hook meters each call as a `judge` usage row. Dev only (session C) |
| langchain-community | — | Pinned to >=0.4,<0.4.2, not used directly. ragas 0.4.3 imports `langchain_community.chat_models.vertexai`, which 0.4.2 removed, so an unpinned lock breaks `import ragas` (caught by the reviewer; `tests/unit/test_scoring.py` now imports the runner so CI catches it) (session C) |

## Web (`web/package.json`, session E)

The browser has no stdlib to beat, so each row says what it replaces instead: hand-written code,
or a heavier library. No router, state library, UI kit or request mocking library.

| Package | Runtime / dev | Instead of | Reason |
|---|---|---|---|
| react, react-dom | runtime | — | The UI (SESSIONS.md stack) |
| openapi-fetch | runtime | hand-written `fetch` wrappers per route | Typed calls from the generated OpenAPI types, about 6 kB |
| eventsource-parser | runtime | a hand-rolled SSE parser | `/ask/stream` is POST, so the browser's `EventSource` cannot be used; this parses the `fetch` body stream |
| openapi-typescript | dev | hand-copied TS types | Generates `src/api/schema.d.ts` from `app.openapi()` (`npm run gen:api`); pinned TypeScript to 5.9 because it accepts ^5 only |
| vite, @vitejs/plugin-react | dev | webpack | Dev server with the API and `/grafana` proxy, production build |
| typescript | dev | — | Strict mode, `noUncheckedIndexedAccess` |
| tailwindcss, @tailwindcss/vite | dev | hand-written CSS | SESSIONS.md stack |
| vitest, jsdom | dev | jest | Shares Vite's config and transforms |
| @testing-library/react, user-event, jest-dom | dev | enzyme | Tests what the user sees and does, not component internals |

## Notes

- `httpx` moved from the dev group to runtime dependencies in session A (still doubles as the
  FastAPI `TestClient` transport in tests).
- `torch` resolves to CPU-only wheels on Linux via a `[tool.uv.sources]` marker pinned to
  `pytorch-cpu`, keeping ~3 GB of CUDA wheels out of the Docker image and CI. macOS dev machines
  use the default PyPI wheel (also CPU-only there). It is listed as a direct dependency, not left
  implicit via `sentence-transformers` — see the table row above for why that's load-bearing.
