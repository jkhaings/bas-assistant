# ADR 0001: Stack decisions

Status: accepted (Sep 26, final weekend scope)

One line per decision, with the reason.

| Decision | Chosen | Alternative | Reason |
|---|---|---|---|
| Language | Python 3.12 | — | Ecosystem match for LlamaIndex, Pydantic v2, LangGraph |
| API framework | FastAPI | Flask, Django | Async, OpenAPI auto-gen, Pydantic v2 native |
| Validation / settings | Pydantic v2 | marshmallow, attrs | First-class FastAPI integration, SecretStr masking |
| Vector store | pgvector + tsvector | Chroma, Qdrant | Single Postgres service, hybrid search in one SQL, no second DB |
| ORM / migrations | SQLAlchemy 2 + Alembic | — | Type-safe, async, industry standard |
| Embeddings | OpenAI text-embedding-3-small via LiteLLM | — | Best quality/cost in class; swappable via alias |
| Reranker | bge-reranker-base (local, sentence-transformers) | Cohere Rerank | Free, no network call, trial key unreliable |
| LLM gateway | LiteLLM | — | Single alias layer, cost logging, virtual keys, fallbacks |
| Fast alias | gpt-4o-mini → gemini-2.0-flash fallback | — | Cheapest capable model |
| Strong alias | claude-sonnet-4-6 → gpt-4o fallback | — | Best reasoning for complex questions |
| Agent graph | LangGraph | raw loop, OpenAI Agents SDK | Named nodes, typed state, pauseable at human gate, replayable |
| Human gate | LangGraph `interrupt` | webhook, Celery | Same thread, resumable, no extra service |
| Ticket backend | Internal Postgres table | Jira | No Jira credentials required for the demo |
| Input/output guard | Presidio + code | Guardrails AI library | Direct control, no extra runtime dependency |
| Observability | Langfuse + Prometheus + Grafana | LangSmith, DataDog | Self-hosted, no extra SaaS cost, Grafana embeds in the app |
| Eval framework | RAGAS + pytest | promptfoo, LangSmith evals | All-Python, integrates with existing test suite |
| Frontend | React + TypeScript + Vite | Next.js, Streamlit | Lightweight, typed, Vite dev-proxy for API |
| Container | Docker Compose | Kubernetes, Azure Container Apps | Single droplet, weekend scope |
| Reverse proxy | Caddy | nginx | Auto-TLS, zero config |
| DNS | Cloudflare on jasonkhaings.com subdomain | — | Free SSL, DDoS protection |
| Auth | "View as" role switcher + admin token | OIDC/Entra ID | No login required for demo; SSO is the documented prod path |
| CI | GitHub Actions, one job, PR only | — | Free for public repos; one job keeps spend at $0 |
| Package manager | uv | pip, poetry | Fastest resolver, lockfile, `uv run` for hooks |
