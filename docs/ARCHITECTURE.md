# bas-assistant: design document

Stack locked (Sep 26, final weekend scope): FastAPI + Pydantic v2 · Postgres 16 + pgvector + tsvector · Redis · Docling (PyMuPDF fallback) · LlamaIndex (ingestion) · OpenAI text-embedding-3-small · local bge-reranker · LiteLLM gateway · GPT-4o-mini → Gemini Flash (fast tier), Claude Sonnet → GPT-4o (strong tier) · LangGraph + Postgres checkpointer + `interrupt` human gate (internal ticket table, no Jira) · guardrails as code: Presidio in/out, injection rail, output validator · "View as" role switcher (no login), admin token for /approve · Langfuse (OTel) · RAGAS + pytest golden set + red-team pytest · Prometheus + Grafana (Budget; Quality & adoption; embedded in the app) · React + TypeScript (Vite) · Docker Compose on the DigitalOcean droplet, Caddy, Cloudflare DNS at bas.jasonkhaings.com · GitHub Actions (one job, PR only, no LLM calls).

Deferred until after the technical round: Slack, n8n, MCP server, Jira, Prefect (ingest is `make ingest`), Cohere, Ollama, promptfoo, LangSmith, k6, MkDocs, Azure/Terraform, Entra ID, Chroma, Guardrails AI library. Sections below that mention these describe the production path, not this weekend's build.

Two interfaces: the web app (product demo; "How I built this" page added last) and Grafana (Budget dashboard, Quality & adoption dashboard). Everything else is a channel into the API.

Deployment decision (Sep 26): public demo link, no login. Hosted with Docker Compose on a DigitalOcean droplet behind Caddy (auto-TLS), Cloudflare DNS on a jasonkhaings.com subdomain (suggest `bas.` or `assistant.`, not `delta.`). Roles are a demo switcher in the UI ("View as: Support / Engineer / Admin"); the Approve action alone requires a shared admin token. OIDC/JWT/Entra and Azure/Terraform move to an optional stretch session. Public exposure makes abuse controls load-bearing: per-IP rate limit, global daily USD cap that pauses the demo with a friendly message, vendor-side hard spend limits, cache.

This file becomes `docs/ARCHITECTURE.md` in the repo. Keep it current-state truthful as things ship.


---

## Build status

| Session | Branch | Status |
|---|---|---|
| 0 — scaffold | `main` | ✅ shipped: `/healthz`, settings, logging, CI |
| A — retrieval | `a-retrieval` | ⏳ not started |
| B — graph | `b-graph` | ⏳ not started |
| C — guardrails | `c-guardrails` | ⏳ not started |
| D — observability | `d-observability` | ⏳ not started |
| E — ship | `e-ship` | ⏳ not started |


## 1. What it does, who it's for

An internal assistant for a building-automation company's support and sales desks. A person asks a product question in Slack or the web app; the assistant finds the exact passages in the company's own documentation, writes a short answer from only those passages, shows the document and page, and says "I don't know" when the docs don't cover it. It can draft a support ticket, but a human approves before anything is filed.

Users and roles (in the demo, chosen with a "View as" switcher; in production, from SSO):
- **support**: asks questions, sees public-tier documents, cannot create tickets.
- **engineer**: everything support can, plus engineer-tier documents, can propose tickets.
- **admin**: everything, approves tickets (requires the admin token in the demo), sees the dashboards.

Corpus (all public): Delta Controls catalog-sheet PDFs, product pages on deltacontrols.com, the O3 help center on Zendesk. Roughly 30 to 60 documents, a few hundred pages, table-heavy.

The twenty questions: derived from the corpus in session 1 (`data/top20_questions.md`), each with the expected source document. They are the golden set for evals and the "twenty questions" from the cover letter.

Non-goals: no free chat about anything outside the corpus, no actions other than the ticket draft, no training or fine-tuning, no scraping of login-gated material.

---

## 2. Data model (Postgres)

| Table | Purpose | Key columns |
|---|---|---|
| documents | one row per source | id, title, source_url, source_type (pdf/page/article), product, doc_type, acl_groups text[], content_hash, parse_quality, ingested_at |
| chunks | child chunks for retrieval | id, document_id, parent_id, page, position, text, tsv tsvector (GIN), embedding vector(1536) (HNSW), metadata jsonb |
| parents | parent chunks for reading | id, document_id, page_start, page_end, text |
| users | people and service accounts | id, email, role, api_key_hash (service accounts), created_at |
| threads | conversations | id, user_id, created_at (LangGraph checkpointer tables live alongside) |
| requests | one row per /ask | id, thread_id, user_id, role, question_redacted, route (fast/strong), decision (answered/abstained/refused/paused/failed), latency_ms, created_at |
| request_chunks | what was retrieved | request_id, chunk_id, rank, score, used_in_answer bool |
| usage | one row per model call | id, request_id, stage (router/embed/answer/judge), alias, model, provider, input_tokens, output_tokens, cached_tokens, usd, latency_ms, cache_hit bool |
| feedback | the letter's first metric | request_id, user_id, value (used_as_is / used_with_edits / not_used), created_at |
| flags | the letter's second metric | request_id, reviewer_id, reason, created_at |
| tickets | proposed and filed tickets | id, request_id, draft jsonb, status (proposed/approved/rejected/filed), approver_id, jira_key |
| audit | append-only log | request_id, actor, action, detail jsonb, created_at |
| budgets | limits | scope (user/team/global), period, usd_limit, tokens_limit |

Cost rolls up from `usage`; adoption from `requests` and `feedback`; quality from `flags` plus eval results stored in `eval_runs`.

---

## 3. Ingestion pipeline (Prefect flow, nightly, and on demand)

1. **Discover**: crawl deltacontrols.com/products (follow Load More), collect product-page URLs and every linked `.pdf`; list O3 help-center articles via the Zendesk Help Center API. Respect robots.txt, one request per second, cache raw bytes in `data/raw/` keyed by URL.
2. **Hash and skip**: content hash per source; unchanged sources are skipped, changed ones re-processed, missing ones marked `retired` (their chunks leave the index).
3. **Parse**: PDFs through Docling (tables preserved as markdown tables); fall back to PyMuPDF and mark `parse_quality` lower. HTML through selectolax, keeping headings. Articles from the API body.
4. **Chunk**: LlamaIndex parent-child. Parent ≈ 1500 tokens by heading/section; child ≈ 300 tokens, overlap 50. A table row never splits across children. Each child records page and parent.
5. **Embed**: batch children through LiteLLM alias `embed`. Cost logged to `usage` with stage `embed`.
6. **Index**: upsert chunks; tsvector generated in SQL; HNSW index on embedding.
7. **Report**: chunk counts by source type, parse-quality distribution, time and cost of the run. Written to the Prefect run log and `eval_runs`.

Idempotent, resumable, and cheap: a nightly run with no changes costs $0.

---

## 4. The request path

```
Slack / Web / MCP
      │
      ▼
 FastAPI /ask ── role header from the UI switcher (or API key for Slack/n8n/MCP) → acl_groups, tool allowlist; global daily USD cap checked first
      │
      ▼
 Input guard: Presidio redaction → Guardrails AI input rails (off-topic, injection patterns) → rate limit + budget check (Redis)
      │
      ▼
 Cache check (Redis, key = normalized question + role + corpus_version) ──hit──▶ return, usd 0
      │ miss
      ▼
 LangGraph graph (section 5) — every node traced
      │
      ▼
 Output guard: validator (citations ⊆ retrieved, no external URLs/images, schema) → PII scan
      │
      ▼
 Persist: requests, request_chunks, usage, audit → stream answer → feedback buttons
```

Target p95 under 4 seconds for a fast-tier answer, under 8 for strong. Streaming starts within 1 second.

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
2. `retrieve` — hybrid search in one SQL: vector top-20 ∪ tsvector top-20 → reciprocal rank fusion → rerank top-30 locally → top-5 parents, filtered by `acl_groups && user.acl_groups`. Edge: best score < threshold → `abstain`; else → `answer`.
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

---

## 6. Cost tracking

**Where the numbers come from.** Every model call, including embeddings and the router, goes through LiteLLM. LiteLLM knows the price sheet per model and returns input, output and cached token counts and USD. The app writes one `usage` row per call with `request_id`, `stage`, `alias`, `model`, `provider`, `cache_hit`.

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

Red-team suite runs on every PR. OWASP LLM Top 10 → control mapping lives in `docs/security.md`.

---

## 8. Observability

- **Traces**: LangSmith (`LANGSMITH_TRACING=true`, zero code) and Langfuse (OpenTelemetry exporter) receive every graph run: node timings, retrieved chunks, model calls with tokens and cost, validation outcomes, gate events.
- **Metrics** (Prometheus, scraped from `/metrics`): requests by decision, latency histogram by route and stage, tokens and USD by model and stage, cache hits, abstains, refusals, validation retries and failures, tool calls by outcome, active threads.
- **Grafana dashboard**: p50/p95 latency, cost per answer, abstain rate, refusal rate, validation failure rate, tool success, requests per user, error rate. Alerts: error rate > 5%, p95 > 8s, budget thresholds, validation failure rate > 2%.
- **Logs**: structured JSON with request_id; no PII, no raw questions (the redacted form only).

---

## 9. Evaluation loop

1. **Golden set**: the twenty questions (growing), each with expected facts, expected source document, and category (spec / ordering / wiring-power / protocol / compatibility / out-of-scope / engineer-only).
2. **promptfoo** on every PR (subset of 15, cost-capped): correct-fact assertions, citation present, abstain when expected, no external URL. Full set locally with `make eval`.
3. **RAGAS** locally: faithfulness, answer relevancy, context precision, context recall, broken down by category and by source document. Low faithfulness on a category is the bias/coverage signal.
4. **LangSmith dataset** with the same twenty and an LLM-as-judge evaluator, for side-by-side comparison of prompt or model changes.
5. **Red team**: pytest suite, every PR.
6. **Load**: k6, 20 virtual users, 2 minutes, recorded in `docs/performance.md`.
7. **Closing the loop**: every flagged answer (section 10) becomes a new golden-set row. Prompts are versioned in git; a prompt change ships only with evals passing.

---

## 10. The two numbers from the cover letter

- **Used without edits**: every answer carries three buttons: used as-is / used with edits / not used. Stored in `feedback`. Reported as % of answered requests, weekly.
- **Sounded right but wasn't**: any user can flag an answer with a reason; stored in `flags`. Automatic proxy: RAGAS faithfulness below threshold on sampled production answers. Reported as % of answered requests, weekly, with the reasons listed.
- **Shadow mode**: four weeks where the team works as normal and the assistant answers beside them. Decision rule written down in advance: expand to the next team if flagged rate stays under 2% and used-as-is is above 60%.

---

## 11. Interfaces and channels

Two interfaces people look at:

1. **The product (web app)**: React + TypeScript. No login (role switcher), threads, streaming answers, citation cards, feedback buttons, a "Show cost" receipt on every answer (route, model, tokens, cost, timings, cache hit), approvals page for admins, and a Dashboards tab that embeds the two Grafana dashboards same-origin. This is the demo. A "How I built this" page is added at the very end (not yet; placeholder route only).
2. **The dashboard (Grafana)**: two dashboards, one Grafana, embedded in the app's Dashboards tab and also reachable at /grafana. Data sources: Prometheus (live ops) and Postgres directly (business numbers).
   - **Budget**: spend today, month-to-date vs budget, cost per answer, cost by model and by stage (router / embed / answer), cost per user and per team, cache hit rate, projected month-end, budget thresholds drawn on the panels.
   - **Quality and adoption**: weekly active users, questions per user, abstain rate, refusal rate, validation failures, p95 latency, ticket escalation rate, and the two letter numbers: used-without-edits % and flagged-wrong %.

Channels into the same API (not screens):
- **Slack**: `/ask-docs question` via Slack Bolt, service-account API key, signing-secret verification, answer with citation links, feedback buttons, "propose ticket" for engineer/admin.
- **MCP server**: FastMCP exposing `search_docs` and `create_ticket` with bearer auth mapped to roles; lets Claude Desktop, Claude Code or any MCP client use the same guarded tools.
- **n8n**: Slack → /ask → approved → Jira, as an exported workflow, to show the low-code path.

Streamlit removed from the stack (Sep 26): Grafana's Postgres data source covers the KPI page.

---

## 12. Deployment

- **Local**: `docker compose up` brings app, Postgres+pgvector, Redis, LiteLLM, Ollama, Langfuse, Prometheus, Grafana, n8n.
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

---

## 14. Open decisions (yours)

1. Chroma as a second backend behind the retriever interface: yes (30 min) or skip.
2. Cohere Rerank flag: only if the trial key works; local reranker is the default either way.
3. OpenAI Agents SDK port of the graph: stretch goal in session 3.
4. Azure OpenAI as a LiteLLM provider: only if the free account allows it.
5. Semantic Kernel sample: stretch in session 8.
