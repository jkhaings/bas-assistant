# Session B handoff: gateway, graph, human gate

Branch `b-graph`, worktree `../bas-assistant-wt/b-graph`. Session A has not been built (no `a-retrieval` branch exists), so this branch runs on an injected retriever: a stub in the app, fixture passages in tests.

## Built

- `config/litellm.yaml`: aliases `fast` (gpt-4o-mini → `fast-fallback` gemini-3.8-flash, `reasoning_effort: low`), `strong` (claude-sonnet-4-6 → `strong-fallback` gpt-4o → the `fast` group), `embed` (text-embedding-3-small). Deployment ids are `<provider>/<model>`; `num_retries: 0`, 30 s timeout per attempt (the app waits 130 s); prompt-cache injection on the Claude system message; vendor keys and master key from env.
- LiteLLM proxy in compose (image pinned by digest, LiteLLM 1.102.1) with its own `litellm` database for virtual keys and `LiteLLM_SpendLogs`.
- Virtual keys `dev` ($5 / 30 d) and `service` ($2 / 30 d): `src/bas_assistant/llm/provision.py`, run by `make litellm-keys` (also at the end of `make up`); creates the key, or updates the budget if it exists. `make litellm-secrets` appends random values for any missing `LITELLM_*` variable to `~/.bas-assistant.env`, without printing them.
- `llm/gateway.py`: `complete()` (strict JSON schema of a Pydantic model) and `embed()` over httpx to the proxy. Model and provider come from `x-litellm-model-id`, USD from `x-litellm-response-cost`, tokens from the body. `GatewayError` after the proxy's own fallbacks.
- `llm/router.py`: `fast` call → `{complexity, topic}`; simple → fast, complex → strong; schema failure → strong; the topic is kept only if it is plain words (it is echoed when abstaining).
- `cost/cache.py`: Redis exact-match cache, key sha256(normalized question, role, `CORPUS_VERSION`), 24 h TTL, first question of a thread only. A hit writes a $0 `usage` row (model `cache`), does not use up the allowance, and seeds the thread's history.
- `cost/usage.py` + `cost/api.py`: one `usage` row per model call; `GET /requests/{id}/receipt` → route, model, tokens, usd, retrieval_ms, rerank_ms, model_ms, total_ms, cache_hit, per-call lines.
- `cost/budget.py`: global daily cap (sum of today's UTC `usage.usd` ≥ `DAILY_USD_CAP`) → 503 `daily_budget_reached` with `resets_at`. Per-user daily question allowance (`USER_DAILY_QUESTIONS`, default 50, Redis) → 429 with `Retry-After`; refunded only when the models are unavailable, to the day it was taken.
- `agent/state.py`: typed `AgentState`, `AnswerOut` `{answerable, answer, citations, confidence, needs_ticket, ticket_draft}`, `turn_input()` that resets per-turn fields while `history` accumulates through a reducer.
- `agent/prompts.py`: invariants-only system prompt (the ticket rule only for roles with `create_ticket`), passages as XML-escaped `<passage>` blocks marked as data, last 6 turns of history, violations appended on retry.
- `agent/validate.py`: citations ⊆ retrieved ids; at least one when answerable; every followable link (any-case http(s), `www.`, inline and reference-style link targets including `//host` and `javascript:`, autolinks, HTML `href`/`src`) must be a retrieved `source_url`; no images (any `![` or `<img`); the same rules on ticket title and body; `needs_ticket` needs a draft.
- `agent/nodes.py` + `agent/graph.py`: route → retrieve → (abstain | answer → validate) → (propose_ticket → human_gate → act) → finish. `answerable: false` → abstained with a fixed message (unless the role may create tickets and a ticket was drafted: fixed message, no citations, recorded as abstained). One retry, then `failed` with a fixed message and an `answer_rejected` audit row. Support gets no ticket, only a note. `human_gate` is a LangGraph `interrupt`. `act` sets the internal ticket to `filed`. Audit rows for proposed / approved / rejected / filed.
- Checkpoints: `PostgresSaver` with a msgpack allowlist of the state classes (`CHECKPOINT_SERDE`).
- `agent/turn.py` + `agent/api.py`: `POST /ask`, `POST /ask/stream` (SSE `node` events, then `answer`; `error` on outage), `POST /approve` (`X-Admin-Token`, constant-time compare, Redis lock against a double resume, released after each resume), `GET /threads/{id}/history` (owner's role only), `GET /tickets` (admin token). A thread can only be continued or read by the role that started it (404 otherwise); 409 while it waits at the gate.
- Alembic revision `0001`: users (three demo users seeded), threads, requests, usage, tickets, audit, per ARCHITECTURE §2 plus `requests.retrieval_ms`, `requests.rerank_ms`, `usage.created_at` (indexed), `audit.id`. `alembic/env.py` excludes LangGraph's checkpoint tables from autogenerate.
- Compose: `postgres` (pgvector pg16, host port 5433, trust auth on 127.0.0.1), `redis`, `litellm`, `app` (runs `alembic upgrade head` first). `deploy/postgres/01-databases.sql` creates `litellm` and `bas_test`.
- Dockerfile fixed (it had never been built in session 0): the uv image tag did not exist (moved to trixie); the venv now stays at `/app/.venv` so console scripts keep valid shebangs; the project is installed non-editable; README is copied for hatchling; alembic files are shipped.
- Tests: 113 unit (the new files cover the gateway, config, ask, cost, gate, memory, stream, validate and provision), 2 integration (real Postgres and Redis in the `bas_test` DB), 5 eval (live models, `make eval`, never in CI). Shared fakes in `tests/fakes.py`.
- Docs: ARCHITECTURE §2, §4, §5, §6, §12, §13 as-built blocks and the build-status row; ADR 0001 fast-fallback row; ADR 0002 dependency lines.

## Verified

Reviewer agent: the first pass returned 10 blocking issues and the second pass 3 more. All are fixed (see "Review fixes" below); the checks below were re-run after the last fix.

**make lint**
```
$ make lint
uv run ruff check src/ tests/ .claude/hooks/
All checks passed!
uv run ruff format --check src/ tests/ .claude/hooks/
52 files already formatted
uv run mypy src/ tests/ .claude/hooks/
Success: no issues found in 52 source files
```

**make test**
```
$ make test
uv run pytest -m unit
........................................................................ [ 63%]
.........................................                                [100%]
113 passed, 7 deselected in 2.96s
```

**make test-int** (real Postgres + Redis; migration drift check included)
```
$ make test-int
DATABASE_URL=postgresql://bas@localhost:5433/bas_test REDIS_URL=redis://localhost:6379/1 uv run alembic upgrade head
DATABASE_URL=postgresql://bas@localhost:5433/bas_test REDIS_URL=redis://localhost:6379/1 uv run alembic check
No new upgrade operations detected.
DATABASE_URL=postgresql://bas@localhost:5433/bas_test REDIS_URL=redis://localhost:6379/1 uv run pytest -m integration
..                                                                       [100%]
2 passed, 118 deselected in 0.93s
```
One integration test pauses a ticket, then builds a new pool, checkpointer and graph (a restart) before approving; the ticket is `filed` and no "unregistered type" deserialization warning is logged.

**docker compose up healthy** (`make up` on a fresh volume, then virtual keys registered; second run updates them)
```
$ docker compose ps
NAME                 STATUS                    PORTS
b-graph-app-1        Up 27 seconds (healthy)   127.0.0.1:8000->8000/tcp
b-graph-litellm-1    Up 54 seconds (healthy)   127.0.0.1:4000->4000/tcp
b-graph-postgres-1   Up 59 seconds (healthy)   127.0.0.1:5433->5432/tcp
b-graph-redis-1      Up 59 seconds (healthy)   127.0.0.1:6379->6379/tcp

$ make litellm-keys   # second run: keys exist, budgets updated
{"ts": "2026-09-26T17:08:41", "level": "INFO", "logger": "__main__", "message": "updated virtual key dev to $5.0/month"}
{"ts": "2026-09-26T17:08:41", "level": "INFO", "logger": "__main__", "message": "updated virtual key service to $2.0/month"}
```

**Acceptance checks with live models** (`make eval`: real proxy, providers, Postgres checkpointer and Redis; fixture passages because there is no corpus yet)
```
$ make eval
tests/eval/test_live_graph.py::test_each_fallback_deployment_still_answers[fast-fallback-gemini/gemini-3.8-flash]
fast-fallback -> 200 gemini/gemini-3.8-flash
PASSED
tests/eval/test_live_graph.py::test_each_fallback_deployment_still_answers[strong-fallback-openai/gpt-4o]
strong-fallback -> 200 openai/gpt-4o
PASSED
tests/eval/test_live_graph.py::test_same_question_twice_costs_nothing_the_second_time
receipt -> {"request_id": "94d875c3-2a40-4182-b8ba-2ae50680842f", "route": "fast", "model": "gpt-4o-mini", "input_tokens": 615, "output_tokens": 55, "cached_tokens": 0, "usd": 0.000125, "retrieval_ms": 12, "rerank_ms": 34, "model_ms": 3473, "total_ms": 3510, "cache_hit": false, "calls": [{"stage": "router", "alias": "fast", "model": "gpt-4o-mini", "provider": "openai", "input_tokens": 136, "output_tokens": 13, "cached_tokens": 0, "usd": 2.8e-05, "latency_ms": 2136, "cache_hit": false}, {"stage": "answer", "alias": "fast", "model": "gpt-4o-mini", "provider": "openai", "input_tokens": 479, "output_tokens": 42, "cached_tokens": 0, "usd": 9.7e-05, "latency_ms": 1337, "cache_hit": false}]}
receipt -> {"request_id": "8d8909e6-c895-432d-b682-72cbd8aca8a0", "route": "fast", "model": "cache", "input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "usd": 0.0, "retrieval_ms": 0, "rerank_ms": 0, "model_ms": 0, "total_ms": 3, "cache_hit": true, "calls": [{"stage": "answer", "alias": "fast", "model": "cache", "provider": "cache", "input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "usd": 0.0, "latency_ms": 0, "cache_hit": true}]}
PASSED
tests/eval/test_live_graph.py::test_complex_question_routes_to_the_strong_model
receipt -> {"request_id": "2ce72e77-0d1f-4b46-9174-a917feee1776", "route": "strong", "model": "claude-sonnet-4-6", "input_tokens": 1005, "output_tokens": 119, "cached_tokens": 0, "usd": 0.004174, "retrieval_ms": 12, "rerank_ms": 34, "model_ms": 7305, "total_ms": 7348, "cache_hit": false, "calls": [{"stage": "router", "alias": "fast", "model": "gpt-4o-mini", "provider": "openai", "input_tokens": 154, "output_tokens": 13, "cached_tokens": 0, "usd": 3.1e-05, "latency_ms": 822, "cache_hit": false}, {"stage": "answer", "alias": "strong", "model": "claude-sonnet-4-6", "provider": "anthropic", "input_tokens": 851, "output_tokens": 106, "cached_tokens": 0, "usd": 0.004143, "latency_ms": 6483, "cache_hit": false}]}
PASSED
tests/eval/test_live_graph.py::test_ticket_request_pauses_and_needs_the_admin_token_to_file
ask engineer -> {"answer": "A support ticket has been drafted for the cracked housing issue on the sample controller at site 12. Replacement parts are ordered through support, so the ticket will route to the right team.", "citations": [{"chunk_id": "c2", "document_title": "Sample Controller Catalog Sheet", "page": 3, "source_url": "https://docs.example.com/sample-controller.pdf", "snippet": "Replacement parts for the sample controller are ordered through support."}], "decision": "paused", "route": "strong", "model": "claude-sonnet-4-6", "request_id": "d092baa3-c61f-411f-b48d-a6d2daba1ca7", "thread_id": "63bcda9a-f2aa-44e4-97c8-b48a1fcb1053", "approval_required": true, "ticket_id": "4c889dbf-aae4-42c5-afba-49e678190c6d", "notes": [], "cache_hit": false}
approve without token -> 401 {"detail":"admin token required"}
approve with token -> 200 {"thread_id":"63bcda9a-f2aa-44e4-97c8-b48a1fcb1053","ticket_id":"4c889dbf-aae4-42c5-afba-49e678190c6d","status":"filed"}
PASSED
====================== 5 passed, 106 deselected in 21.35s ======================
```
Re-run after the second review's fixes (rebuilt app, same five tests):
```
approve without token -> 401 {"detail":"admin token required"}
approve with token -> 200 {"thread_id":"170400f5-8ec3-4f22-b721-bf293566f9e1","ticket_id":"4d958b4f-7738-4192-8572-0b7ba1e80c53","status":"filed"}
====================== 5 passed, 115 deselected in 16.04s ======================
```
The complex question was answered by Claude with `answerable: false` (the synthetic passages hold no pre-ordering checklist), so its decision is `abstained` after a strong answer call; the receipt shows route, model and the separate router cost.

**Forced fallback, live** (throwaway proxy on port 4001 from `config/litellm.yaml` with the named deployments given an invalid vendor key; LiteLLM refuses `mock_testing_fallbacks` unless a `dangerously_allow_…` flag is set, which stays off)
```
# broken: fast-primary
fast: HTTP 200 {"x-litellm-model-id": "gemini/gemini-3.8-flash", "x-litellm-attempted-fallbacks": "1", "x-litellm-response-cost": "9e-06"} content='ok'
# broken: all-strong
strong: HTTP 200 {"x-litellm-model-id": "openai/gpt-4o-mini", "x-litellm-attempted-fallbacks": "2", "x-litellm-response-cost": "3.15e-06"} content='Ok.'
```

**A forced fabricated citation fails closed** (unit, fake proxy): `tests/unit/test_validate.py::test_fabricated_citation_is_retried_then_fails_closed` returns `decision=failed`, the fixed message, no citations, neither the fabricated id nor its text in the response, 2 answer calls, one `answer_rejected` audit row. Disabling the citation check makes it fail:
```
$ (citation check disabled; run before the review fixes added tests to this file) uv run pytest -m unit tests/unit/test_validate.py
FAILED tests/unit/test_validate.py::test_fabricated_citation_is_retried_then_fails_closed
FAILED tests/unit/test_validate.py::test_rejected_answer_is_retried_with_the_violations_listed
2 failed, 8 passed in 0.90s
```

**HTTP surface of the compose app** (no corpus in the app until A merges, so questions abstain after routing)
```
$ curl -s http://localhost:8000/healthz
{"status":"ok"}

(same question as engineer, first time for that role)
{"answer":"I couldn't find this in the documentation. I searched for: Red5 PLUS 1146 vs 1180 controllers. Try naming the product model, or ask about a spec, protocol or wiring detail.","citations":[],"decision":"abstained","route":"strong","model":null,"request_id":"586cc3ee-5160-4df4-89db-1b07b0b40f7b","thread_id":"e7d4fa02-55c3-4031-a14a-baece8165dc3","approval_required":false,"ticket_id":null,"notes":[],"cache_hit":false}

$ curl -s http://localhost:8000/requests/586cc3ee-5160-4df4-89db-1b07b0b40f7b/receipt
{"request_id":"586cc3ee-5160-4df4-89db-1b07b0b40f7b","route":"strong","model":null,"input_tokens":155,"output_tokens":20,"cached_tokens":0,"usd":0.000035,"retrieval_ms":0,"rerank_ms":0,"model_ms":1366,"total_ms":1391,"cache_hit":false,"calls":[{"stage":"router","alias":"fast","model":"gpt-4o-mini","provider":"openai","input_tokens":155,"output_tokens":20,"cached_tokens":0,"usd":0.000035,"latency_ms":1366,"cache_hit":false}]}

$ curl -s -X POST http://localhost:8000/ask -H 'X-Demo-Role: engineer' -H 'Content-Type: application/json' -d '{"question":"Compare the Red5 PLUS 1146 and 1180 controllers and explain step by step which to wire for a 24 VAC retrofit."}'
{"answer":"I couldn't find this in the documentation. I searched for: Red5 PLUS 1146 vs 1180 controllers. Try naming the product model, or ask about a spec, protocol or wiring detail.","citations":[],"decision":"abstained","route":"strong","model":null,"request_id":"2791268a-4b17-4551-a378-333568ba964d","thread_id":"09e9f814-21f6-4ea6-a54a-60c0ba9b6912","approval_required":false,"ticket_id":null,"notes":[],"cache_hit":true}

$ curl -s http://localhost:8000/requests/40b9376b-47a6-472e-a89f-27a5a04513a1/receipt
{"request_id":"40b9376b-47a6-472e-a89f-27a5a04513a1","route":"strong","model":"cache","input_tokens":0,"output_tokens":0,"cached_tokens":0,"usd":0.0,"retrieval_ms":0,"rerank_ms":0,"model_ms":0,"total_ms":1,"cache_hit":true,"calls":[{"stage":"answer","alias":"strong","model":"cache","provider":"cache","input_tokens":0,"output_tokens":0,"cached_tokens":0,"usd":0.0,"latency_ms":0,"cache_hit":true}]}

$ curl -s -N -X POST http://localhost:8000/ask/stream -H 'X-Demo-Role: support' -H 'Content-Type: application/json' -d '{"question":"Which wiring terminals does the DAC-633PoE use for 24 VAC?"}'
event: node
data: {"node": "route"}

event: node
data: {"node": "retrieve"}

event: node
data: {"node": "abstain"}

event: node
data: {"node": "finish"}

event: answer
data: {"answer":"I couldn't find this in the documentation. I searched for: DAC-633PoE wiring terminals. Try naming the product model, or ask about a spec, protocol or wiring detail.","citations":[],"decision":"abstained","route":"fast","model":null,"request_id":"d34821ae-7ca2-4086-b51c-6727183f347e","thread_id":"9bdee1e7-c6d0-4eb8-9908-827b36800a2d","approval_required":false,"ticket_id":null,"notes":[],"cache_hit":false}

# the engineer's thread, asked about as support
$ curl -s -X POST http://localhost:8000/ask -H 'X-Demo-Role: support' -H 'Content-Type: application/json' -d '{"question":"and the 1180?","thread_id":"e7d4fa02-55c3-4031-a14a-baece8165dc3"}'
{"detail":"thread not found"}
$ curl -s http://localhost:8000/threads/e7d4fa02-55c3-4031-a14a-baece8165dc3/history -H 'X-Demo-Role: support'
{"detail":"thread not found"}
$ curl -s http://localhost:8000/threads/e7d4fa02-55c3-4031-a14a-baece8165dc3/history -H 'X-Demo-Role: engineer'
[{"question":"Compare the Red5 PLUS 1146 and 1180 controllers and explain step by step which to wire for a 24 VAC retrofit.","answer":"I couldn't find this in the documentation. I searched for: Red5 PLUS 1146 vs 1180 controllers. Try naming the product model, or ask about a spec, protocol or wiring detail."}]

$ curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8000/approve -H 'Content-Type: application/json' -d '{"thread_id":"e7d4fa02-55c3-4031-a14a-baece8165dc3","approve":true}'
401
$ curl -s -X POST http://localhost:8000/approve -H 'X-Admin-Token: wrong' -H 'Content-Type: application/json' -d '{"thread_id":"e7d4fa02-55c3-4031-a14a-baece8165dc3","approve":true}'
{"detail":"admin token required"}
$ curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/tickets
401
$ curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8000/ask -H 'Content-Type: application/json' -d '{"question":"Compare ..."}'
422
```

**LiteLLM's own records** (virtual-key budgets and per-call spend, database `litellm`)
```
 key_alias | max_budget | budget_duration |  spend
-----------+------------+-----------------+----------
 dev       |          5 | 30d             | 0.009400
 service   |          2 | 30d             | 0.000000

   model_group   |            model            | calls |   usd
-----------------+-----------------------------+-------+----------
 fast            | openai/gpt-4o-mini          |     6 | 0.000254
 fast-fallback   | gemini/gemini-3.8-flash     |     2 | 0.000169
 strong          | anthropic/claude-sonnet-4-6 |     2 | 0.008925
 strong-fallback | openai/gpt-4o               |     1 | 0.000053
```

**Secrets**
```
$ gitleaks dir . --redact --no-banner
INF scanned ~807359 bytes (807.36 KB) in 212ms
INF no leaks found
$ uv run pre-commit run --all-files
No API key shapes in staged files........................................Passed
gitleaks — scan staged diff for secrets..................................Passed
ruff format..............................................................Passed
ruff check --fix.........................................................Passed
```

### Review fixes (first reviewer pass, all blocking items)

1. mypy failure in the integration test: fixed. The integration tier now uses its own `bas_test` DB and Redis db 1, so its fake-proxy costs never reach the app's spend totals.
2. Link bypasses (`HTTPS://`, `//host`, `www.`, `javascript:`): the validator covers every followable link form, and ticket text too.
3. A correct "not covered" answer ended as `failed`: `AnswerOut.answerable` added; false → `abstained` with a fixed message.
4. Allowance refunded on validator rejections: the refund is now only for model outages.
5. Thread history crossed roles (engineer-only content could reach support): thread owner checked on follow-ups and history.
6. Cheap lockout of a role's shared allowance: cache hits no longer count. The per-role nature is documented; per-IP limiting is session C.
7. 73-line migration `upgrade()`: split per table.
8. Literal Postgres password: gone (trust auth on 127.0.0.1, local compose only).
9. App-level strong→fast fallback duplicated LiteLLM: deleted, now `strong: [strong-fallback, fast]` in the proxy config.
10. Missing tests (router bad output, stream error, provision): added.

Second pass (3 blocking, all fixed):
11. Reference-style links and images and HTML `href`/`src` passed the validator: now caught, including any `![`.
12. Support role plus `answerable: false` plus a drafted ticket showed "I drafted a ticket": it now abstains.
13. The `/approve` lock was never released, so a second ticket on the same thread got 409: released in `finally`, with a test.
Also from that pass: no citation cards and `abstained` recorded for a ticket the docs don't cover; migration column types; app timeout 130 s to cover a nested fallback; merge note on `down -v` for trust auth.

## Deferred

- Rebase on session A: A has not been built, so there is nothing to rebase on. Merge notes below.
- Replace session A's embedding provider with the `embed` alias: A's provider does not exist yet. `gateway.embed()` is built and unit-tested, and is unused until A wires it in.
- Answered and ticket flows over curl against the compose app: the app has no corpus until A (it wires `main.no_corpus_yet`). Those flows were verified live in-process by `make eval` (real proxy and models, fixture passages).
- Token streaming in `/ask/stream`: deliberately not built. It streams node events and then the validated answer, because nothing reaches the user before `validate` passes it.
- `request_chunks` rows and metrics in `finish`: the tables and metrics belong to sessions A and D.
- A live check of the daily cap: covered by unit tests (`test_daily_cap_reached_returns_503_with_reset_time`) and the Postgres query by an integration test; session E's acceptance trips it live at $0.01.

## Known gaps

Each has a matching `TODO` in the source.

- `llm/gateway.py`: a virtual-key budget refusal from LiteLLM surfaces as 503 `model_unavailable`, not 429.
- `agent/turn.py`: the stored question is only regex-redacted (emails, key shapes). The Postgres checkpoints hold the raw question and history with no expiry. Session C: Presidio before storage and before the graph.
- `agent/turn.py`: with no login, every visitor of a role is the same demo user, so the "per-user" allowance is a per-role quota. Session C's per-IP limiter is the per-visitor control.
- `agent/api.py`: errors other than `GatewayError` (for example a DB error, or a malformed proxy response) leave the request's decision NULL and the allowance spent.
- `config/litellm.yaml`: Claude prompt caching is configured but inactive. The system prompt (about 300 tokens) is under Anthropic's 1,024-token minimum; receipts show `cached_tokens` 0.
- `settings.py`: the app still requires the vendor keys, and the shared env file gives the LiteLLM container `ADMIN_TOKEN` and the Grafana password. Split the env files in session E.
- `main.py`: `no_corpus_yet` retriever until A merges.
- An abstained answer is not quite $0: the router call comes before retrieval (about $0.00003).
- LiteLLM refuses `mock_testing_fallbacks` by design. The live fallback check is manual (above), and `make eval` checks that each fallback deployment still answers.

## Merge notes

- **Env vars (new)**: `LITELLM_MASTER_KEY`, `LITELLM_API_KEY` (the app's virtual key, dev budget), `LITELLM_SERVICE_KEY`, all required by `make check-env` and already in Jason's `~/.bas-assistant.env`. `DATABASE_URL` is required by Settings (compose sets it; it is now a `SecretStr`). Optional: `USER_DAILY_QUESTIONS` (50), `CORPUS_VERSION` ("0"), `REDIS_URL`, `LITELLM_BASE_URL`. `.env.example` is updated.
- **Dependencies added**: langgraph, langgraph-checkpoint-postgres, langchain-core, psycopg[binary], psycopg-pool, sqlalchemy, alembic, redis, httpx (runtime); fakeredis, httpx2, pyyaml, types-pyyaml (dev). ADR 0002 has a line for each. For `uv.lock`, run `uv lock`; never hand-merge.
- **Alembic**: A also creates a first revision for the full §2 schema, so `alembic heads` will show 2 after the rebase. Resolution: keep A's revision as the base, delete `alembic/versions/0001_graph_tables.py`, and make sure A's schema includes B's extra columns: `requests.retrieval_ms`, `requests.rerank_ms`, `usage.created_at` + `ix_usage_created_at`, `audit.id`, and nullable `usage.request_id`. Keep B's `alembic/env.py` (checkpoint-table exclusion) and `script.py.mako`. Run `make test-int`; it ends with `alembic check`.
- **Tables module**: `src/bas_assistant/db.py` defines B's six tables with SQLAlchemy Core. If A defines ORM models for the same tables, keep one definition. B's code imports `db.users/threads/requests/usage/tickets/audit` and `db.metadata`; point those at A's tables or add A's tables to `db.py`.
- **Retriever**: replace `main.no_corpus_yet` with an adapter over A's `VectorStore` that returns `agent.state.Retrieval(passages=[Passage(chunk_id, document_title, page, source_url, text, score)], retrieval_ms, rerank_ms)`. The threshold stays in the retriever (empty result → abstain). Pass `user.acl_groups` through; B already does.
- **`/ask`**: B's graph-backed `/ask` supersedes A's retrieval-only `/ask`. Keep A's `/documents`. `roles.py` (role → `acl_groups`, tools) may overlap A's role-header mapping; keep one.
- **Cache**: after A merges, bump `CORPUS_VERSION`, or run `docker compose exec redis redis-cli FLUSHDB`. The stub retriever's abstains are cached for 24 h under version "0".
- **Compose**: Postgres is on host port **5433** (5432 is taken on this machine by another project) with trust auth, and mounts `deploy/postgres/` init SQL that creates the `litellm` and `bas_test` databases. If A also adds a `postgres` service, keep B's definition. Trust auth and the init SQL apply only when the volume is first created, so an existing volume made with a password needs `docker compose down -v` (loses local data) before `make up`.
- **Makefile**: `up` now also runs `litellm-keys`; `test-int` and `eval` are implemented (B's `eval` runs `pytest -m eval`; session C adds the golden set and RAGAS to the same marker); new `litellm-keys` and `litellm-secrets` targets. `ingest` and `redteam` are still stubs.
- **Dockerfile**: base images moved to Debian trixie (`ghcr.io/astral-sh/uv:0.11.16-python3.12-trixie-slim`, `python:3.12-slim-trixie`), WORKDIR `/app`.
- **ADR 0001**: the fast fallback is gemini-3.8-flash; gemini-2.0-flash and 2.5-flash return 404 (retired).
- **CI**: unchanged; `pytest -m unit` needs no services (SQLite, fakeredis, fake proxy).
