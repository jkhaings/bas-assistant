# bas-assistant: design document

Stack locked (Sep 26, final weekend scope): FastAPI + Pydantic v2 · Postgres 16 + pgvector + tsvector · Redis · Docling (pypdfium2 fallback — already a Docling dependency, avoids adding AGPL PyMuPDF) · LlamaIndex (ingestion) · OpenAI text-embedding-3-small · local MiniLM cross-encoder reranker (bge-reranker-base until session D, ADR 0003) · LiteLLM gateway · GPT-4o-mini → Gemini Flash (fast tier), Claude Sonnet → GPT-4o (strong tier) · LangGraph + Postgres checkpointer + `interrupt` human gate (internal ticket table, no Jira) · guardrails as code: Presidio in/out, injection rail, output validator · "View as" role switcher (no login), admin token for /approve · Langfuse (OTel) · RAGAS + pytest golden set + red-team pytest · Prometheus + Grafana (Budget; Quality & adoption; embedded in the app) · React + TypeScript (Vite) · Docker Compose on the DigitalOcean droplet, Caddy, Cloudflare DNS at bas.jasonkhaings.com · GitHub Actions (one job, PR only, no LLM calls).

Deferred until after the technical round: Slack, n8n, MCP server, Jira, Prefect (ingest is `make ingest`), Cohere, Ollama, promptfoo, LangSmith, k6, MkDocs, Azure/Terraform, Entra ID, Chroma, Guardrails AI library. Sections below that mention these describe the production path, not this weekend's build.

Two interfaces: the web app (product demo; "How I built this" page added last) and Grafana (Budget dashboard, Quality & adoption dashboard). Everything else is a channel into the API.

Deployment decision (Sep 26): public demo link, no login. Hosted with Docker Compose on a DigitalOcean droplet behind Caddy (auto-TLS), Cloudflare DNS on a jasonkhaings.com subdomain (suggest `bas.` or `assistant.`, not `delta.`). Roles are a demo switcher in the UI ("View as: Support / Engineer / Admin"); the Approve action alone requires a shared admin token. OIDC/JWT/Entra and Azure/Terraform move to an optional stretch session. Public exposure makes abuse controls load-bearing: per-IP rate limit, global daily USD cap that pauses the demo with a friendly message, vendor-side hard spend limits, cache.

This file becomes `docs/ARCHITECTURE.md` in the repo. Keep it current-state truthful as things ship.


---

## Build status

| Session | Branch | Status |
|---|---|---|
| 0 — scaffold | `main` | Shipped: `/healthz`, settings, logging, CI |
| A — retrieval | `a-retrieval` | Shipped: ingest (crawl/parse/chunk/embed), hybrid retrieval, `GET /documents`; its retrieval-only `/ask` is now `POST /search` |
| B — graph | `b-graph` | Merged to main: LiteLLM proxy (fast / strong / embed, embeddings included), router, Redis cache, `usage` + receipt, daily cap + allowance, LangGraph with human gate on a Postgres checkpointer, retrieve node on A's hybrid search, `/ask`, `/ask/stream`, `/approve`, `/threads/{id}/history`, `/tickets`, `/requests/{id}/receipt` |
| C — guardrails | `c-guardrails` | Merged to main: Presidio input redaction before storage and models, injection/off-topic rail (patterns + router flags → `refuse`), output PII check, per-IP limiter, one limit error shape, audit row on every decision, `/approve` tool allowlist, key-budget 429, prompt versioning, golden set (`make eval`) + RAGAS + `eval_runs` + `GET /evals/latest`, red team (`make redteam`), `docs/security.md`. Also retrieval (document title in lexical rank and rerank, threshold 0.7) and crawler retries |
| D — observability | `d-observability` | Built on branch, not merged: reranker loaded at startup, 15 candidates, MiniLM cross-encoder (ADR 0003); OpenTelemetry traces to self-hosted Langfuse; Prometheus `/metrics`; Grafana Budget and Quality & adoption dashboards on `dash_*` views with alert rules; `POST /requests/{id}/feedback` and `/flag`; JSON logs with request_id and trace_id |
| E — ship | `e-ship` | Not started |


## 1. What it does, who it's for

An internal assistant for a building-automation company's support and sales desks. A person asks a product question in Slack or the web app; the assistant finds the exact passages in the company's own documentation, writes a short answer from only those passages, shows the document and page, and says "I don't know" when the docs don't cover it. It can draft a support ticket, but a human approves before anything is filed.

Users and roles (in the demo, chosen with a "View as" switcher; in production, from SSO):
- **support**: asks questions, sees public-tier documents, cannot create tickets.
- **engineer**: everything support can, plus engineer-tier documents, can propose tickets.
- **admin**: everything, approves tickets (requires the admin token in the demo), sees the dashboards.

Corpus (all public): Delta Controls catalog-sheet PDFs, product pages on deltacontrols.com, the O3 help center on Zendesk (deferred — see session A's build notes). As ingested Sep 27 2026: 112 documents (70 catalog PDFs, 42 product pages), 1459 parents, 1502 chunks, table-heavy.

The twenty questions: derived from the corpus in session 1 (`data/top20_questions.md`), each with the expected source document. They are the golden set for evals and the "twenty questions" from the cover letter.

Non-goals: no free chat about anything outside the corpus, no actions other than the ticket draft, no training or fine-tuning, no scraping of login-gated material.

---

## 2. Data model (Postgres)

| Table | Purpose | Key columns |
|---|---|---|
| documents | one row per source | id, title, source_url, source_type (pdf/page/article), product, doc_type, acl_groups text[], content_hash, parse_quality, ingested_at |
| chunks | child chunks for retrieval | id, document_id, parent_id, page, position, text, tsv tsvector (GIN), embedding vector(1536) (HNSW), metadata jsonb |
| parents | parent chunks for reading | id, document_id, page_start, page_end, text |
| users | people and service accounts | id, email, role, team, api_key_hash (service accounts), created_at |
| threads | conversations | id, user_id, created_at (LangGraph checkpointer tables live alongside, from session B) |
| requests | one row per /ask | id, thread_id, user_id, role, question_redacted, route (fast/strong), decision (retrieved/abstained today; answered/refused/paused/failed join from B/C), latency_ms, created_at |
| request_chunks | what was retrieved | request_id, chunk_id, rank, score, used_in_answer bool |
| usage | one row per model call | id, request_id (nullable — ingestion embeds have none), stage (router/embed/answer/judge), alias, model, provider, input_tokens, output_tokens, cached_tokens, usd, latency_ms, cache_hit bool, created_at |
| feedback | the letter's first metric | request_id, user_id, value (used_as_is / used_with_edits / not_used), created_at |
| flags | the letter's second metric | request_id, reviewer_id, reason, created_at |
| tickets | proposed and filed tickets | id, request_id, draft jsonb, status (proposed/approved/rejected/filed), approver_id, jira_key, created_at |
| audit | append-only log | id, request_id, actor, action, detail jsonb, created_at |
| budgets | limits | id, scope (user/team/global), period, usd_limit, tokens_limit |
| eval_runs | golden-set and red-team results | id, kind (golden/redteam), corpus_version, prompt_version, scores jsonb, cost_usd, created_at |

Cost rolls up from `usage`; adoption from `requests` and `feedback`; quality from `flags` plus eval results stored in `eval_runs`. All tables exist as of session A (one migration each for corpus+users, then the rest of activity) so no later session alters a table another session depends on; sessions B–D are the first to *write* to most of the activity rows beyond users/threads/requests/request_chunks/usage.

**Session B additions (migration `0003`)**: `requests.retrieval_ms` and `requests.rerank_ms`; `requests.decision` and `requests.latency_ms` become nullable, because a graph turn writes its request row before it runs and fills them in when it closes; `ix_usage_created_at` for the daily cap. `Ticket.draft` and `Audit.detail` use a JSON type with a JSONB variant (same DDL on Postgres) so unit tests can create them on SQLite. LangGraph's checkpoint tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`) are created by `PostgresSaver.setup()` at startup and excluded from Alembic autogenerate (`db/migrations/env.py`). LiteLLM keeps virtual keys and spend logs (`LiteLLM_SpendLogs`) in a separate `litellm` database on the same server (`deploy/postgres/init.sql`); `make test-int` uses `bas_test`. Since session C the graph only ever sees the Presidio-redacted question, so the checkpoint tables hold redacted questions and answers; they still have no expiry. `budgets` exists but is unused: limits are env settings plus LiteLLM virtual-key budgets.

**Session C additions (migration `0004`)**:
- `requests.prompt_version` records `agent.prompts.PROMPT_VERSION` for each request.
- `eval_runs.scores` uses the same JSON-with-JSONB-variant type as `tickets.draft` (same Postgres
  DDL; `alembic check` is clean), so unit tests can create it on SQLite.
- `eval_runs` is written by `eval/ragas_run.py` (kind `golden`) and by the red-team suite (kind
  `redteam`).
- `usage` gains stage `judge` rows, one per RAGAS judge call.
- New `audit` actions: `input_redacted`, `input_refused`, `decision`, `rate_limited`,
  `daily_cap_reached`, `allowance_used`, `approve_refused`.

**Session D additions (migration `0005`, after C's `0004`)**:
- Fifteen `dash_*` views behind every Postgres panel in Grafana. `dash_questions` is closed `/ask` turns only: `/search` diagnostics have no route and are left out. It is the building block for the others and holds request, thread and user ids, so it is the one view Grafana cannot read.
- A `grafana_reader` role that may select the fourteen panel views and nothing else, with a connection limit of 5 and a 5 s `statement_timeout`. `TEMP` is revoked from `PUBLIC` on the database, so no role can fill the disk with temp tables. The role is created NOLOGIN; `make grafana-db-user` sets its password from `GRAFANA_DB_PASSWORD`.
- `budgets` rows: global/monthly $5 (the app's LiteLLM virtual-key budget) and global/daily, which the app rewrites from `DAILY_USD_CAP` at every start (`cost/budget.sync_daily_cap`). The cap is still enforced from the setting; the row lets the dashboard show the cap that is actually enforced.
- `dash_eval_latest` reads `eval_runs.scores->'overall'` when it is an object, else the top-level numeric keys: the contract for session C's RAGAS rows.
- `feedback` and `flags` are written by the endpoints in §10.

---

## 3. Ingestion pipeline (`make ingest`, manual — Prefect is the deferred production path)

Built in session A, `src/bas_assistant/ingest/`:

1. **Discover**: read `product-sitemap.xml` for every product page URL (robots.txt-endorsed; the "Load More" AJAX isn't reverse-engineered), plus a starter list of 12 known catalog PDFs tried directly by URL. Each product page's `.downloads-list a.download-link` is scanned for PDF links matching an allowlist (catalog/datasheet/protocol/spec), capped at 40 PDFs total. robots.txt sets `Crawl-delay: 10`, so the crawler waits 10s between real requests (stricter than the original 1 req/s plan) and caches raw bytes in `data/raw/` keyed by a hash of the URL — a re-run with a warm cache does no network I/O at all. The Zendesk O3 help center is not crawled (deferred; see below).
2. **Hash and skip**: content hash per source (raw bytes for a PDF; extracted text for HTML, since HTML carries per-request nonces that would defeat a raw-byte hash) — unchanged sources are skipped, changed ones replaced in one transaction. There is no `retired` state yet: a source that disappears from discovery simply stops being re-ingested; its existing rows are not deleted.
3. **Parse**: PDFs through Docling (`do_table_structure=True`, tables become markdown tables, one page at a time up to 20 pages); on any Docling failure or empty output, falls back to pypdfium2's plain-text extraction and records `parse_quality="fallback"`. HTML product pages through selectolax: headings, paragraphs, list items and tables in document order (selectolax's compound CSS selectors do **not** preserve document order — verified against real markup — so content is walked depth-first instead), nav/footer/script/style dropped.
4. **Chunk**: LlamaIndex `MarkdownNodeParser` splits each page into heading sections (further split by `SentenceSplitter` if a section exceeds ~1500 tokens) as parents; `SentenceSplitter(chunk_size=300, chunk_overlap=50)` with a custom line-aware tokenizer splits each parent into children so a markdown table row is never split across children. Each child records page, parent, and (via the parent/document relationship) product, doc_type, acl_groups, and source_url.
5. **Embed**: children are embedded in batches of 100 through a thin `EmbeddingProvider` (an OpenAI-compatible `/v1/embeddings` client) — not yet the LiteLLM alias `embed`, which is session B's job; the base URL and model are both settings, so B repoints them without touching this code. One `usage` row per batch, `stage="embed"`, `request_id` null.
6. **Index**: SQLAlchemy upserts documents/parents/chunks in one transaction per source; `tsv` is a Postgres `GENERATED ALWAYS AS (to_tsvector(...))` column with a GIN index; `embedding` has an HNSW index (`vector_cosine_ops`).
7. **Report**: `python -m bas_assistant.ingest` logs one structured line: documents ingested/updated/skipped/failed by source type, parents and chunks written, the parse_quality distribution, embed tokens and USD, and elapsed time.

Idempotent and resumable (a re-run with no changes costs $0 in both crawl and embed time); not yet scheduled — `make ingest` is a manual step until a later session wants a cron/Prefect flow.

Session C: a fetch that fails on a network error, a 5xx or a 429 is retried with tenacity. Backoff is exponential from the 10 s crawl delay, 4 attempts. On a final failure the URL is logged, that source is skipped for this run, and the crawl goes on. Before this, one DNS error aborted the whole crawl. A 4xx is skipped immediately. A robots.txt fetch that still fails after its retries ends the crawl, loudly.

**Deferred from this session:** Prefect scheduling (ingest is a manual `make ingest`), the Zendesk O3 help center, and document retirement (removed sources' chunks are not pruned). Since the session B merge, embeddings go through the LiteLLM proxy's `embed` alias with the app's virtual key (`embed_base_url`, `embed_model`, `litellm_api_key`), and USD comes from the proxy's `x-litellm-response-cost` header, with `embed_usd_per_mtok` as the fallback.

---

## 4. The request path

**`POST /search`** (session A's retrieval-only endpoint, formerly `/ask`; kept for inspecting retrieval on its own). `POST /ask` is the agent graph, below; its retrieve node runs the same `retrieve()`:

```
Web (curl, for now)
      │
      ▼
 FastAPI POST /search ── X-Demo-Role header (default "support", 422 if unrecognised) → acl_groups
      │
      ▼
 retrieve(): embed the question → pgvector top-20 ∪ tsvector top-20 (both acl_groups &&-filtered)
             → reciprocal rank fusion → top-15 → local cross-encoder rerank
             → group by parent, best child per parent → top-5
             → best score < rerank_threshold ? abstain : citations
      │
      ▼
 Persist: one `threads` row (one per request — session B adds multi-turn reuse),
          one `requests` row (decision = retrieved|abstained), `request_chunks` for
          the top-15 reranked, one `usage` row for the query embed call
      │
      ▼
 Response: {request_id, answer: null, citations[], retrieved[], abstained, timings}
```

The reranker is the only non-trivial cost in retrieval, and it runs on CPU. Measured in session D
(ADR 0003):
- bge-reranker-base over 30 candidates took 13–20 s per question in the container.
- Since session D, `cross-encoder/ms-marco-MiniLM-L-6-v2` over 15 candidates, loaded at app startup
  (`retrieval.rerank.load_reranker` in the lifespan), takes rerank p50 979 ms and p95 2,177 ms over
  the 40 golden `/search` calls. `rerank_threshold` is 0.8, and `CORPUS_VERSION` moved to "2" so no
  answer cached under the old reranker is served.

**Retrieval as of session C**:
- The lexical candidates match and rank on `setweight(to_tsvector(documents.title), 'A') ||
  chunks.tsv`. It is computed per query, outside the GIN index, which is fine at about 1.5k chunks.
- The cross-encoder scores `"{document title}\n{chunk text}"`. A short spec section
  ("## Power / 24 VDC (20 W max)") rarely names its product, and sibling catalog sheets repeat
  sections word for word, so without the title the reranker cannot tell them apart.
- `rerank_threshold` is re-tuned from 0.5 to 0.7. Every answerable golden row now tops out at 0.93
  or above, and every must-abstain row at 0.53 or below (`data/top20_questions.md`).
- `/search` also passes the per-IP limiter. It redacts the question before the query embedding
  and stores only the redacted text.

**As built (session B)**, `src/bas_assistant/agent/api.py` and `agent/turn.py`:
1. `X-Demo-Role` header through A's `api/roles.demo_role` (default support, 422 if unrecognised) → seeded demo user, `acl_groups`, tool allowlist (`tools_for_role`).
2. An existing `thread_id` must belong to that role's user (404 otherwise, so one role never sees another's history) and must not be waiting at the gate (409). `GET /threads/{id}/history` applies the same ownership check.
3. Global daily USD cap: sum of today's (UTC) `usage.usd` ≥ `DAILY_USD_CAP` → 503 `{reason: "daily_budget_reached", resets_at}`.
4. Cache check, first question of a thread only (follow-ups depend on history). A hit costs $0 and skips step 5.
5. Daily allowance: `USER_DAILY_QUESTIONS` (default 50) per user per UTC day, Redis counter → 429 `daily_allowance_used` with `Retry-After`. With no login every visitor of a role is the same demo user, so in the demo this is a per-role quota; per-visitor limiting is session C's per-IP limiter.
6. `requests` row. Since C, the question is redacted by Presidio in `open_turn` before the cache lookup, and nothing downstream sees the raw text: not the row, the checkpoints, the history or the models. `prompt_version` is stored on the row, and an `input_redacted` audit row counts the entities per type.
7. Graph (section 5). A gateway failure after all fallbacks → 503 `model_unavailable`, request `failed`, allowance refunded (to the day it was taken). An answer the validator rejects keeps its place in the allowance, since its model calls were billed.
8. `requests` updated with route, decision, latency, retrieval and rerank ms; `request_chunks` written for the passages the graph read (rank, score, `used_in_answer` = cited); answered or abstained first turns are cached.

`POST /ask/stream` takes the same path and sends SSE events: `node` as each node finishes, then `answer`. Answer tokens are not streamed, because nothing reaches the user before `validate` passes it.

**As built (session C)**, in the order a request meets them:
0. The per-IP sliding window (`guardrails/limits.per_ip_limit`, a route dependency on `/ask`,
   `/ask/stream`, `/approve` and `/search`, so it runs before any row is written). The limit is
   `IP_RATE_LIMIT` requests per minute (default 20) → 429 `rate_limited`.
   It keys on `request.client.host`. Behind Caddy that is one shared address until uvicorn trusts
   the proxy's `X-Forwarded-For` (`FORWARDED_ALLOW_IPS`, session E).
- Every limit answers `detail = {reason, message, resets_at}` with `Retry-After` when it can:
  - `rate_limited` (429)
  - `daily_allowance_used` (429)
  - `daily_budget_reached` (503)
  - `key_budget_reached` (429: LiteLLM's `budget_exceeded` refusal of the virtual key)
  - `model_unavailable` (503)
- `/ask/stream` sends the same dict as its `error` event.
- Audit rows `rate_limited` (once per burst), `daily_cap_reached` and `allowance_used` have no
  request id.
- Every closed request writes an audit `decision` row with decision, route and prompt_version,
  cache hits included.

Since session D, any error in `/ask` or `/ask/stream` closes the request as `failed` (and refunds the allowance) before the error propagates, so crashes show up in metrics and on the dashboards. Before, only gateway failures did.

**Deferred**: API keys for Slack / n8n / MCP (post-weekend).

---

## 5. Agent workflow (LangGraph)

**State** (typed, Pydantic):
```
question, question_redacted, user{id, role, acl_groups, tools_allowed}, thread_id,
route: fast|strong, retrieved: [chunk refs with scores], answer: {text, citations[], confidence},
needs_ticket: bool, ticket_draft, approval: pending|approved|rejected|none,
decision, errors[], usage_so_far
```

**Nodes and edges**:

1. `route` — fast model, structured output `{complexity: simple|complex, topic}`. Edge: always → `retrieve`. Logged to `usage` stage `router`.
2. `retrieve` — hybrid search in one SQL: vector top-20 ∪ tsvector top-20 → reciprocal rank fusion → rerank top-15 locally (top-30 until session D) → top-5 parents, filtered by `acl_groups && user.acl_groups`. Edge: best score < threshold → `abstain`; else → `answer`.
3. `abstain` — deterministic, no model call. "I couldn't find this in the documentation. I searched: … Try: …" Decision = abstained. → `finish`.
4. `answer` — model per `route`, system prompt with invariants only, passages wrapped as data. Structured output: `{answer, citations: [chunk_id], confidence, needs_ticket, ticket_draft?}`. Prompt caching on the system prompt. → `validate`.
5. `validate` — code, no model. Citations must be a subset of retrieved ids; no URLs outside `documents.source_url`; no images; schema valid. Fail → one retry of `answer` with the mismatch list appended; second fail → decision = failed, safe message. Pass → `needs_ticket` ? `propose_ticket` : `finish`.
6. `propose_ticket` — only if `create_ticket` ∈ user.tools_allowed, else strip and note. Draft stored in `tickets` (status proposed). → `human_gate`.
7. `human_gate` — LangGraph `interrupt`. Graph state checkpointed to Postgres; API returns the answer plus `approval_required` and the thread id. Resumes when POST /approve arrives from an admin. Approved → `act`; rejected → `finish`.
8. `act` — Jira REST create issue; write `jira_key`; audit. Failures are retryable and never lose the draft. → `finish`.
9. `finish` — persist request, request_chunks, usage totals, decision; emit metrics.

**Why a graph and not a loop**: every step is a named node with typed state, so it can be traced, tested in isolation, paused at the gate, resumed after a restart, and replayed from any checkpoint. The model makes exactly two decisions (route, answer); everything else is code.

**Memory**: the checkpointer keeps thread history; follow-ups ("what about the Edge model?") see prior turns. History is trimmed to the last 6 turns before the answer call to cap tokens.

**Tool authorization**: tools are declared per role in config, enforced in `propose_ticket` and again in the MCP server. The model never sees a tool it isn't allowed to use.

**As built (session B)**, `src/bas_assistant/agent/`:
- **State**: `AgentState` in `state.py`: request_id, question, user, route, topic, retrieved, retrieval_ms, rerank_ms, draft_raw, draft, answer_model, attempts, validation_errors, ticket_id, approval, approver_id, decision, final_answer, notes, history. `history` has an append reducer and accumulates across a thread's turns; every other field is reset per turn. The redacted question lives on the `requests` row, not in state.
- **route**: `llm/router.py`, `fast` alias, `max_tokens` 60. Output that fails the schema routes to `strong`. The topic is echoed in the abstain message, so anything but short plain words (no `:`, `/` or `.`) is dropped.
- **retrieve**: `agent/corpus.search_corpus` runs session A's `retrieve()` (query embed through the `embed` alias → pgvector ∪ tsvector, ACL-filtered → RRF → local rerank → top-5 parents). Below `rerank_threshold` it returns no passages → `abstain`. Each passage is a whole parent, cited by the id of its best child chunk. The query embedding's cost is written as a `usage` row (stage `embed`). The graph takes the retriever as an injected `Retriever(question, acl_groups) -> Retrieval`, so unit tests use a fixed one.
- **answer**: alias from `route`, `max_tokens` 700, temperature 0, strict JSON schema of `AnswerOut`. Passages are rendered as escaped `<passage id=… document=… page=… source_url=…>` blocks. `AnswerOut` = `{answerable, answer, citations, confidence, needs_ticket, ticket_draft}`.
- **validate**: parses `AnswerOut` (a schema failure counts as a violation). `answerable: false` → decision `abstained` with the fixed abstain message (the model's wording is never shown), unless the role may create tickets and the model drafted one. Otherwise: citations ⊆ retrieved chunk ids; at least one citation when answerable; every followable link (any-case `http(s)://`, `www.`, inline link targets including `//host` and `javascript:`, reference definitions `[1]: url`, `<scheme:…>` autolinks, HTML `href`/`src`) must be a retrieved passage's `source_url` (stricter than all of `documents`); no images (any `![` or `<img`); the same link and image rules apply to the ticket title and body; `needs_ticket` requires a draft. A ticket for something the passages don't cover shows a fixed message instead of the model's text, with no citation cards, and the request is recorded as `abstained` once the gate resolves. One retry with the violations listed, then decision `failed`, a fixed safe message, and an `answer_rejected` audit row.
- **propose_ticket**: a role without `create_ticket` gets no ticket and a note in the response; its system prompt says `needs_ticket` is always false. Otherwise a `tickets` row (proposed) and a `ticket_proposed` audit row.
- **human_gate**: `interrupt`. `POST /approve` with `X-Admin-Token` (constant-time compare; 401 otherwise) resumes with `{approve, approver_id}`; the ticket becomes approved or rejected, with an audit row. A Redis `SET NX` lock per thread, released when the resume finishes (60 s expiry as a backstop), turns a concurrent second approval into 409 instead of a second resume; the response reports the stored outcome.
- **act**: internal table only: status `filed` and a `ticket_filed` audit row (no Jira).
- **finish**: final decision, and appends the turn to `history`. The API writes the `requests` row around the graph.
- **Checkpoints**: `PostgresSaver` with a msgpack allowlist of the state classes (`graph.CHECKPOINT_SERDE`), so a checkpoint can only rebuild those types. A thread paused at the gate survives an app restart (integration test).
- **Memory**: the last 6 turns go into the answer prompt; `GET /threads/{id}/history` returns all turns.

**As built (session C)**:
- **Graph**: `screen → (refuse | route)`, `route → (refuse | retrieve)`, `refuse → finish`. Two new
  nodes; the model still makes two decisions.
- **screen**: code only, $0. A narrow regex list of instruction-override phrasings
  (`guardrails/input.injection_pattern`). "ignore the wiring instructions" is not one of them.
- **route**: the router call also returns `is_injection`, `is_off_topic` and `reason`, with
  `max_tokens` 120. Off-topic means nothing to do with building automation or the company;
  refund, policy and support questions are on topic, and abstain when the docs do not cover them.
- **refuse**: decision `refused` with a fixed plain message per kind, and an `input_refused`
  audit row (rail `pattern|model`, kind, reason). The model's reason is never shown, and a
  refusal is not cached. State gains `refusal`, `refusal_rail` and `refusal_reason`.
- **retrieve**: takes `acl_groups` from `acl_groups_for_role(role)` and raises `PermissionError`
  if the user context disagrees.
- **validate**: the validator moved to `guardrails/output.py`. It adds a Presidio scan of the
  answer and ticket text: an email, phone, person or street address that no retrieved passage
  contains is a violation. The violation names the type, not the value. Public contact details
  quoted from the docs pass.
- **Prompts**: `agent/prompts/` holds `answer_system.md`, `ticket_rule.md`, `no_ticket_rule.md`
  and `router.md`. `PROMPT_VERSION` is the first 12 hex characters of the sha256 over them. It is
  recorded on `requests` and `eval_runs`, and is part of the answer-cache key, so a prompt edit
  invalidates cached answers.
- **/approve**: needs the admin token and an `X-Demo-Role` whose tools include `approve_ticket`
  (admin only); otherwise 403 and an `approve_refused` audit row. The approver id is that role's
  demo user.

Since session D the six work nodes run inside a trace span each (`graph.traced`), and request metrics are counted where the API closes the request row (`records.close_request`), not in `finish`, because cache hits never enter the graph (§8).

**Deferred**: Jira in `act` (post-weekend); the MCP server.

---

## 6. Cost tracking

**Where the numbers come from.** Every model call, including embeddings and the router, goes through LiteLLM. LiteLLM knows the price sheet per model and returns input, output and cached token counts and USD. The app writes one `usage` row per call with `request_id`, `stage`, `alias`, `model`, `provider`, `cache_hit`.

Since the session B merge this holds for embeddings too: session A's `EmbeddingProvider` calls the proxy's `embed` alias with the app's virtual key, and records the deployment and USD the proxy reports.

**Attribution.** `requests` carries user and role; users carry a team tag. Cost per request = sum of its usage rows. Cost per user, per team, per day, per stage = one GROUP BY. The router's cost is visible separately, so you can prove routing pays for itself.

**Controls, in order of where they bite.**
1. LiteLLM virtual keys with monthly USD budgets: `dev`, `service-slack`, `service-n8n`, one per team later. Over budget → LiteLLM refuses, app returns 429 with Retry-After.
2. App-level daily allowance per user (Redis counter). Over → 429, and the UI says when it resets. Server-side failures refund the allowance (the vib-agent rule).
3. `max_tokens` on every call; history trimmed; five passages, not twenty.
4. Exact-match cache: repeated questions cost $0 and are counted as cache hits.
5. Prompt caching on the ~1,500-token system prompt: cached input tokens billed at a fraction.
6. Routing: simple questions never touch the strong model.

**Reporting.**
- Grafana: USD per hour, per model, per stage; cache hit rate; cost per answered request (rolling 24h).
- Grafana Budget dashboard (Postgres data source): cost per answer, per user, per team, month to date vs budget, projected month-end.
- `docs/cost-model.md`: measured cost per simple and complex answer, blended cost at the observed simple/complex ratio, monthly projection at 50 / 200 / 1,000 questions per day, plus fixed costs (Azure Container App at min-replicas 0, Postgres, Redis).
- Alerts: 50 / 80 / 100 percent of the monthly budget; any single request over $0.10; cost per hour 3× the 7-day average (a loop or abuse).
- Azure Cost Management budget for the infrastructure side.

**Forecast method.** cost_per_answer × answers_per_day × 22 × (1 + 20% buffer). Re-fit monthly from real `usage` data. Written down before launch so the number is a prediction, not an excuse.

**As built (session B)**:
- **Gateway**: `src/bas_assistant/llm/gateway.py` calls the LiteLLM proxy over HTTP by alias; no vendor SDK in the app. `config/litellm.yaml`: `fast` = gpt-4o-mini → `fast-fallback` gemini-3.8-flash (`reasoning_effort: low`); `strong` = claude-sonnet-4-6 → `strong-fallback` gpt-4o → the `fast` group; `embed` = text-embedding-3-small. `num_retries: 0` (the fallback is the retry) and a 30 s timeout per attempt; the app's HTTP timeout is 130 s, longer than the proxy's worst case (four 30 s attempts if `fast`'s own fallback also applies). gemini-2.0-flash (in the original plan) and 2.5-flash return 404 (retired); verified live Sep 26. `tests/eval` also calls the `fast-fallback` and `strong-fallback` groups directly (still through the proxy), the one exception to the three-alias rule, so a retired fallback shows up before the day a primary fails.
- **Numbers**: each `usage` row takes model and provider from the `x-litellm-model-id` header (deployment id `<provider>/<model>`, so a fallback is attributed to the model that answered), USD from `x-litellm-response-cost`, tokens from the response body. A cache hit writes one $0 row with model `cache`.
- **Receipt**: `GET /requests/{id}/receipt` → route, model, tokens, usd, retrieval_ms, rerank_ms, model_ms, total_ms, cache_hit, and one line per call, so router cost is visible separately.
- **Controls built**: (1) virtual keys `dev` ($5 / 30 days) and `service` ($2 / 30 days), registered by `make litellm-keys`; the per-channel keys wait for those channels. (2) Allowance of 50 questions per user per UTC day (per role in the demo; cache hits are free), refunded only when the models are unavailable; global daily cap `DAILY_USD_CAP` (default $3) → 503. (3) `max_tokens` 60 for the router, 700 for the answer; 6 turns of history. (4) Exact-match cache, 24 h TTL, key = normalized question + role + `CORPUS_VERSION`. (5) Prompt caching is configured on the Claude deployment (`cache_control_injection_points`) but inactive: the system prompt is about 300 tokens, under Anthropic's 1,024-token minimum, and live receipts show `cached_tokens` 0. (6) Routing.
- LiteLLM also logs every call with its cost in `LiteLLM_SpendLogs` (database `litellm`).

Since session C, a LiteLLM key-budget refusal (429, error type `budget_exceeded`, checked live with a `max_budget: 0` key) raises `KeyBudgetError` and returns 429 `key_budget_reached`. The allowance is refunded. RAGAS judge calls are written as `usage` rows with stage `judge` and no request id, so the daily cap counts them.

**Reporting as built (session D)**: the Budget dashboard (§11) reads `usage`, `requests` and `budgets` through the `dash_*` views: spend today against the enforced cap, month-to-date against the $5 key budget with a linear month-end projection, cost per answer, cost by model and stage, cost per user and team, cache hit rate, and USD per hour by model from Prometheus. Alerts fire at 50, 80 and 100% of the daily cap.

**Deferred**: `docs/cost-model.md` (E); per-request ($0.10) and hourly-spike cost alerts; per-team budgets (the Budget dashboard groups by `users.team`, but every demo user is team `default`).

---

## 7. Guardrails, placed

| Fence | Where | What | Test |
|---|---|---|---|
| Input | API layer | Presidio redaction; rails for off-topic and injection phrasing; rate limit; budget | PII probe, "ignore your instructions" |
| Retrieval | SQL | `acl_groups` filter before the model sees anything; passages wrapped as data | support user never receives engineer-only chunk; poisoned chunk with instructions is quoted, not obeyed |
| Model | prompt + config | invariants-only system prompt; low temperature; structured output; tool allowlist per role | schema violations caught |
| Output | `validate` node | citations ⊆ retrieved; no external URLs or images; PII scan; one retry then fail closed | fabricated citation forced via fake LLM → failed decision |
| Action | `human_gate` | no write without admin approval; scoped Jira token | support cannot reach `act` |
| Audit | everywhere | append-only rows; no raw PII | every red-team case has an audit row |

**As built (session C)**: every fence above exists. `docs/security.md` has the table with file
locations and tests, and the OWASP LLM Top 10 (2025) mapping.
- The red-team suite (`tests/redteam/`, `make redteam`) runs against the live stack, locally
  only, because CI makes no LLM calls. Last live run: 6/6 on Sep 27 (`outputs/HANDOFF_C.md`;
  the latest golden run, 21/22, is in `eval/results/latest.md`). Cases:
  - direct injection
  - instructions planted in a document (the case checks that the planted chunk was retrieved)
  - an image-exfiltration request
  - PII in the question: checked absent from the requests row, the audit detail, the checkpoints,
    the history and the `app`/`litellm` container logs
  - support asking for a ticket and trying `/approve`
  - off-topic
- Each case asserts an audit row, and the run writes an `eval_runs` row with kind `redteam`.
- The unit tier mirrors each fence with the fake LLM, and CI runs that on every PR.
- Deferred: a larger NER model, and PII expiry for LiteLLM's spend logs (see `docs/security.md`).

---

## 8. Observability

- **Traces**: Langfuse (OpenTelemetry exporter) receives every graph run: node timings, retrieval, model calls with tokens and cost, validation outcomes, gate events. (LangSmith was dropped from scope on Sep 26.)
- **Metrics** (Prometheus, scraped from `/metrics`): requests by decision, latency histogram by route and stage, tokens and USD by model and stage, cache hits, abstains, refusals, validation retries and failures, tool calls by outcome, active threads.
- **Grafana dashboard**: p50/p95 latency, cost per answer, abstain rate, refusal rate, validation failure rate, tool success, requests per user, error rate. Alerts: error rate > 5%, p95 > 8s, budget thresholds, validation failure rate > 2%.
- **Logs**: structured JSON with request_id; no PII, no raw questions (the redacted form only).

**As built (session D)**, `src/bas_assistant/observability/`, `deploy/{prometheus,grafana,langfuse}/`:
- **Traces**: OpenTelemetry, exported over OTLP/HTTP to a self-hosted Langfuse v4 (`deploy/langfuse/compose.yml`: web on 127.0.0.1:3001, worker, ClickHouse, MinIO, and its own Postgres and Redis). LangSmith is not used. `FastAPIInstrumentor` makes one root span per API request (`/healthz` and `/metrics` excluded). Inside it:
  - `node <name>` spans for route, retrieve, answer, validate, propose_ticket and act. Each records what the node decided (route, decision, attempts, violation and passage counts, retrieval/rerank ms), never text. `human_gate` is not wrapped, because `interrupt()` raises to pause.
  - A generation span per model call (`llm fast|strong|embed`), with model, tokens and USD from the proxy's headers.
  - `retrieval.search` and `retrieval.rerank` spans.
  - `gate paused` / `gate resumed` events.
  - The trace carries `langfuse.session.id` = thread id (so a thread's `/ask` and `/approve` group together), user = role, and metadata request_id, decision, route and cache_hit.
  - Its input is the redacted question, the same string as `requests.question_redacted`; its output is the validated answer. Prompts, passages and the raw question are never attached, and a unit test checks that no span attribute holds the raw question.
  - Without `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` nothing is exported (unit tests, CI).
- **Metrics** (`GET /metrics`, scraped by Prometheus every 15 s):
  - `bas_requests_total{decision,route}` and `bas_request_latency_seconds{route}`, counted where every request closes (`agent/records.close_request`); abstains and refusals are decisions.
  - `bas_stage_latency_seconds{stage}` for retrieval, rerank, router, embed and answer.
  - `bas_tokens_total{model,stage,kind}` and `bas_usd_total{model,stage}` (from `record_usage`).
  - `bas_cache_hits_total`, `bas_validation_retries_total`, `bas_validation_failures_total`, `bas_tickets_total{status}`, `bas_feedback_total{value}`, `bas_flags_total`.
  - `bas_active_threads`, the turns running right now; the metric is named "active threads" in the plan.
  - `bas_http_requests_total{method,route,status}` by route template (the error-rate source; probes and scrapes are not counted).
  - Labels never carry ids or users. Per-user numbers come from Postgres.
- **Grafana** 13.2 at `/grafana` (127.0.0.1:3000):
  - Anonymous Viewer, embedding allowed, sub-path serving, Explore off, admin password from env.
  - Data sources: Prometheus, and Postgres as `grafana_reader`, a role that can select only the panel views from migration 0005. Anonymous viewers can send any SQL through a data source, so the role is the boundary: no readable view exposes a question, answer, flag reason, email or id. The role has 5 connections, Grafana at most 4, and a 5 s statement timeout.
  - Grafana's container reads only `~/.bas-assistant-grafana.env` (its admin and reader passwords), never the vendor keys, because it is the one publicly reachable service.
  - Two provisioned, read-only dashboards: **Budget** (`bas-budget`) and **Quality & adoption** (`bas-quality`, including hourly p50/p95 `rerank_ms`); panels in §11.
  - Five alert rules: API 5xx share above 5%, p95 answer latency above 8 s, and daily spend at 50, 80 and 100% of the cap. The error-rate rule also counts the daily-cap 503, so a tripped cap fires it alongside the 100% rule. `bas_requests_total` counts a request when it first closes, so a gated request stays `paused` there; `/approve` updates only the row, which the Postgres panels read.
- **Logs**: every JSON line carries the OTel `trace_id` when a span is active, and request logs carry `request_id`, so a log line leads to its trace. No question text is logged.

**Deferred**: an alert contact point (alerts show in Grafana's alerting page only); Langfuse on the droplet (drop order #2, decided in session E); the tool-call metric (the only tool is the ticket, counted by `bas_tickets_total`); the validation-failure-rate alert (the failures counter and panel exist). Session E's Caddy must not route `/metrics` or Langfuse publicly without auth.

---

## 9. Evaluation loop

1. **Golden set**: the twenty questions (growing), each with expected facts, expected source document, and category (spec / ordering / wiring-power / protocol / compatibility / out-of-scope / engineer-only).
2. **promptfoo** on every PR (subset of 15, cost-capped): correct-fact assertions, citation present, abstain when expected, no external URL. Full set locally with `make eval`.
3. **RAGAS** locally: faithfulness, answer relevancy, context precision, context recall, broken down by category and by source document. Low faithfulness on a category is the bias/coverage signal.
4. **LangSmith dataset** with the same twenty and an LLM-as-judge evaluator, for side-by-side comparison of prompt or model changes.
5. **Red team**: pytest suite, every PR.
6. **Load**: k6, 20 virtual users, 2 minutes, recorded in `docs/performance.md`.
7. **Closing the loop**: every flagged answer (section 10) becomes a new golden-set row. Prompts are versioned in git; a prompt change ships only with evals passing.

**As built (session C)**: `make eval` runs the golden set, then RAGAS.
- **Case file**: `eval/golden.jsonl` is generated from the table in `data/top20_questions.md` by
  `python -m bas_assistant.evals.golden`. A unit test keeps the two in sync.
- **Golden run** (`tests/eval/test_golden.py`): asks each case through the live `/ask`, with the
  cache entry dropped first. Rows 1–18 are asked as support, rows 19–20 as support and engineer:
  22 calls.
  - An answer row passes when the decision is `answered` and a citation's `source_url` contains the
    expected product key.
  - An abstain row passes when the decision is `abstained` with no citations.
  - Per-case results go to `eval/results/golden-latest.jsonl` (gitignored).
- **RAGAS** (`eval/ragas_run.py`, dev only; judge metering, category means and the summary are in
  `evals/scoring.py`, which is unit-tested): faithfulness, answer relevancy, context precision (with
  reference) and context recall over the answered rows.
  - The contexts are the parents the answer model read (`request_chunks` → `parents`). The
    reference is the expected fact.
  - Judge: the `fast` alias. Embeddings: the `embed` alias. Both go through langchain-openai at
    the LiteLLM proxy with the app's virtual key.
  - httpx hooks meter each judge call as a `usage` row (stage `judge`). The rows are written even
    when RAGAS fails halfway. RAGAS telemetry is off (`RAGAS_DO_NOT_TRACK`).
  - It writes an `eval_runs` row with kind `golden`. Its `scores` document is
    `{run_at, corpus_version, golden: {passed, total, rate}, failures, overall: {n, faithfulness,
    answer_relevancy, context_precision, context_recall}, by_category: {<category>: same}}`.
    `overall` and `by_category` are what session D's Quality & adoption dashboard reads. Cost is
    the golden answers' usage plus the judge usage.
  - It also writes `eval/results/latest.md`, which make prints.
- **`GET /evals/latest`** returns the newest `golden` and `redteam` runs for the Evals tab.
- **Red team**: section 7.
- **Deferred**: promptfoo, the LangSmith dataset and k6 (out of weekend scope). Flag-to-golden-row
  is a manual step.

---

## 10. The two numbers from the cover letter

- **Used without edits**: every answer carries three buttons: used as-is / used with edits / not used. Stored in `feedback`. Reported as % of answered requests, weekly.
- **Sounded right but wasn't**: any user can flag an answer with a reason; stored in `flags`. Automatic proxy: RAGAS faithfulness below threshold on sampled production answers. Reported as % of answered requests, weekly, with the reasons listed.
- **Shadow mode**: four weeks where the team works as normal and the assistant answers beside them. Decision rule written down in advance: expand to the next team if flagged rate stays under 2% and used-as-is is above 60%.

**As built (session D)**, `src/bas_assistant/feedback/api.py`:
- `POST /requests/{id}/feedback {value: used_as_is|used_with_edits|not_used}` and `POST /requests/{id}/flag {reason}` both return 204.
- The caller is the `X-Demo-Role` user. A request that belongs to another role is 404, the same rule as thread history.
- One vote per person per answer; a new vote replaces the old.
- The flag reason is redacted before it is stored (regex today; Presidio from C).
- The Quality dashboard shows used-as-is and flagged as % of answered questions per week, never the reasons, because the dashboard is public.

The RAGAS-faithfulness proxy on sampled production answers is not built.

---

## 11. Interfaces and channels

Two interfaces people look at:

1. **The product (web app)**: React + TypeScript. No login (role switcher), threads, streaming answers, citation cards, feedback buttons, a "Show cost" receipt on every answer (route, model, tokens, cost, timings, cache hit), approvals page for admins, and a Dashboards tab that embeds the two Grafana dashboards same-origin. This is the demo. A "How I built this" page is added at the very end (not yet; placeholder route only).
2. **The dashboard (Grafana)**: two dashboards, one Grafana, embedded in the app's Dashboards tab and also reachable at /grafana. Data sources: Prometheus (live ops) and Postgres directly (business numbers).
   - **Budget**: spend today, month-to-date vs budget, cost per answer, cost by model and by stage (router / embed / answer), cost per user and per team, cache hit rate, projected month-end, budget thresholds drawn on the panels.
   - **Quality and adoption**: weekly active users, questions per user, abstain rate, refusal rate, validation failures, p95 latency, ticket escalation rate, and the two letter numbers: used-without-edits % and flagged-wrong %.

   - **As built (session D)**: `deploy/grafana/dashboards/{budget,quality}.json`, provisioned read-only.
     - Budget:
       - Spend today, and as % of the daily cap (50/80/100 thresholds).
       - Month to date: USD, % of budget, and projected month-end.
       - Spend per day against dashed cap lines.
       - USD per hour by model (Prometheus); cost per answer; cost by model and stage.
       - Cost per user and team; cache hit rate.
     - Quality & adoption:
       - Adoption: active users and questions per user this week; questions and active users by week.
       - The two letter numbers: used-without-edits % and flagged %.
       - Tickets: escalation rate and tickets by status.
       - Latency: hourly p50/p95 rerank time against a 3 s line, and hourly p50/p95 answer latency against the 8 s line.
       - Abstain, refusal and failure rates; p95 by stage (Prometheus); validation retries and failures.
       - Latest evaluation scores from `eval_runs`.
     - `deploy/grafana/iframe-test.html` embeds both in plain iframes.

Channels into the same API (not screens):
- **Slack**: `/ask-docs question` via Slack Bolt, service-account API key, signing-secret verification, answer with citation links, feedback buttons, "propose ticket" for engineer/admin.
- **MCP server**: FastMCP exposing `search_docs` and `create_ticket` with bearer auth mapped to roles; lets Claude Desktop, Claude Code or any MCP client use the same guarded tools.
- **n8n**: Slack → /ask → approved → Jira, as an exported workflow, to show the low-code path.

Streamlit removed from the stack (Sep 26): Grafana's Postgres data source covers the KPI page.

---

## 12. Deployment

- **Local**: `docker compose up` brings app, Postgres+pgvector, Redis, LiteLLM, Ollama, Langfuse, Prometheus, Grafana, n8n.
  As built (sessions A+B): `make up` starts `migrate` (one-shot `alembic upgrade head`), app, Postgres + pgvector (127.0.0.1:5433, password from the env file), Redis (127.0.0.1:6379, for host-side tests) and the LiteLLM proxy (127.0.0.1:4000, image pinned by digest, its `DATABASE_URL` assembled in the container from `POSTGRES_PASSWORD`), then registers the virtual keys.
  Session D adds:
  - Prometheus (127.0.0.1:9090) and Grafana (127.0.0.1:3000, served at `/grafana`).
  - Langfuse through `include: deploy/langfuse/compose.yml` (web on 127.0.0.1:3001, plus worker, ClickHouse, MinIO, Postgres 17 and Redis of its own, none published). Its containers read only `~/.bas-assistant-langfuse.env`, because its variable names collide with ours and it has no use for the vendor keys.
  - `make observability-secrets` writes that file once, and appends `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `GRAFANA_DB_PASSWORD` to the main env file.
  - `make up` ends with `make grafana-db-user`.

  Ollama and n8n are not in compose.
- **Public demo**: the same Compose file (production profile: no Ollama if the droplet is small, Langfuse optional) on a DigitalOcean droplet. Caddy reverse proxy with auto-TLS: `/` → web app + API, `/grafana` → Grafana with anonymous Viewer access limited to the two dashboards. Cloudflare DNS A record on the jasonkhaings.com subdomain. Secrets in the droplet's env file only. `deploy/deploy.sh` pulls the tagged image and restarts.
- **CI**: one GitHub Actions workflow, one job (pull_request only, concurrency cancel-in-progress): gitleaks, ruff, mypy, `pytest -m unit`. uv cache on. No LLM calls, no image push, no `secrets.` refs.
- **Abuse controls (public link)**: per-IP sliding-window rate limit, global daily USD cap (demo pauses with a message and a reset time), vendor-side hard spend limits on every key, exact-match cache, `max_tokens` caps. Admin token required for /approve.
- **Stretch (optional session)**: Terraform → Azure Container Apps + Key Vault + App Insights, Entra ID OIDC login replacing the role switcher. Adds the Microsoft names to the story; not needed for the demo link.

---

## 13. Failure modes and what happens

| Failure | Behaviour |
|---|---|
| Strong model down | LiteLLM falls back to GPT-4o; if all strong fail, route to fast; if all fail, clear "service unavailable", request marked failed, allowance refunded |
| Retrieval finds nothing | abstain, no model call, $0 |
| Model cites a passage it wasn't given | validate fails → retry → fail closed; never shown |
| Injection in a document | passage is data; validator blocks resulting URLs/actions; audit row |
| User over budget | 429 with reset time |
| Jira down | draft kept, action retryable, admin notified |
| Postgres down | app returns 503; no partial writes (transactions) |
| Corpus changed | nightly re-index; corpus_version bumps; cache invalidated |

**As built (session B)**: strong model down (the proxy falls back to gpt-4o, then to the `fast` group; if everything fails, 503 `model_unavailable` with the request `failed` and the allowance refunded; the fallbacks were verified live by forcing the primaries to fail); fabricated citation (retry, then fail closed); user over budget (429 with `Retry-After`; daily cap 503 with `resets_at`). Session C: virtual-key budget spent → 429 `key_budget_reached`, request `failed`, allowance refunded; a crawl fetch that fails is retried with backoff, then skipped with its URL logged. Retrieval finding nothing abstains without an answer call, but not at exactly $0: the router call comes before retrieval (about $0.00003). Not built yet: Jira, the Postgres-down 503, corpus-change invalidation beyond the `CORPUS_VERSION` setting.

---

## 14. Open decisions (yours)

1. Chroma as a second backend behind the retriever interface: yes (30 min) or skip.
2. Cohere Rerank flag: only if the trial key works; local reranker is the default either way.
3. OpenAI Agents SDK port of the graph: stretch goal in session 3.
4. Azure OpenAI as a LiteLLM provider: only if the free account allows it.
5. Semantic Kernel sample: stretch in session 8.
