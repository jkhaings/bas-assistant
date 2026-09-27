# Session D handoff: reranker latency, then observability

Branch `d-observability`, worktree `../bas-assistant-wt/d-observability`, from `main` at `47cebd9`.

**The stack in this session ran on offset host ports.** Session C's stack held the standard ones the whole time. The override was a scratchpad compose file selected with `COMPOSE_FILE`, never committed: app 8001, Postgres 5434, Redis 6380, LiteLLM 4001, and an app image tag of `bas-assistant-app:d-observability`. Grafana (3000), Langfuse (3001) and Prometheus (9090) are on their committed ports. `make test-int` hardcodes 5433 and would have hit C's `bas_test`, so its three commands were run by hand against 5434 (below). Everything committed uses the standard ports.

## Built

**Reranker latency** (Jason's request, before the D block; decision and numbers in `docs/adr/0003-reranker.md`):
- **Loaded once at startup.** `retrieval/rerank.load_reranker` is called in `main._serve`, so `/healthz` goes green only with the model in memory. It was already cached per process, but loaded lazily on the first request. The app healthcheck's `start_period` is now 120 s.
- **Not emulated.** Every image is `linux/arm64`, and the container reports `aarch64` with 8 torch threads (below).
- **30 → 15 candidates** (`retrieval/pipeline.FUSED_TOP_N`).
- **Still over 3 s, so MiniLM.** The reranker is now `cross-encoder/ms-marco-MiniLM-L-6-v2`, with an explicit sigmoid so scores stay in 0–1, and `rerank_threshold` moves from 0.5 to 0.8 (tuned on the golden set). `CORPUS_VERSION` defaults to "2", so answers cached under the old reranker are not served. predict() no longer prints tqdm bars into the JSON logs.

**Observability** (the D block):
- **Traces**: OpenTelemetry over OTLP/HTTP to a self-hosted Langfuse v4 (`deploy/langfuse/compose.yml`: web on 127.0.0.1:3001, worker, ClickHouse, MinIO, and its own Postgres 17 and Redis; org, project, keys and login created headlessly). `observability/tracing.py` holds the provider, the generation attributes, the trace tags and the client-detail hook.
  - `FastAPIInstrumentor` gives one root span per request (no `/healthz` or `/metrics`, no ASGI send/receive spans), with the user agent and client address blanked.
  - `node <name>` spans (`agent/graph.traced`) for route, retrieve, answer, validate, propose_ticket and act, with what each decided.
  - `llm fast|strong|embed` generation spans with model, tokens and USD.
  - `retrieval.search` / `retrieval.rerank` spans.
  - `gate paused` / `gate resumed` events.
  - Session = thread id, user = role, input = the redacted question, output = the validated answer. Never the raw question, prompts or passages.
- **Metrics**: `GET /metrics` (`observability/metrics.py`) serves requests by decision and route, latency histograms by route and by stage, tokens and USD by model and stage, cache hits, validation retries and failures, tickets by status, feedback, flags, active threads, and HTTP responses by route template and status. Prometheus v3.15.0 on 127.0.0.1:9090 scrapes the app every 15 s.
- **Grafana** 13.2.2 at `localhost:3000/grafana`:
  - Settings: anonymous Viewer, embedding allowed, sub-path serving, Explore off, admin password from env.
  - Its container reads only `~/.bas-assistant-grafana.env`.
  - Provisioned data sources: Prometheus, and Postgres as `grafana_reader`.
  - Two read-only dashboards in `deploy/grafana/dashboards/`: **Budget** and **Quality & adoption**. The Quality dashboard carries hourly p50/p95 rerank_ms against a 3 s line, and answer latency against the 8 s line.
  - Five alert rules: 5xx > 5%, p95 > 8 s, and spend at 50/80/100% of the daily cap.
  - `deploy/grafana/iframe-test.html` embeds both dashboards in plain iframes.
- **Migration `0004_dashboards`**:
  - 15 `dash_*` views, one behind every Postgres panel.
  - `grafana_reader`: SELECT on the 14 panel views only (not `dash_questions`, which holds ids), connection limit 5, `statement_timeout` 5 s; TEMP revoked from PUBLIC.
  - `budgets` rows. The daily one is rewritten from `DAILY_USD_CAP` at every app start (`cost/budget.sync_daily_cap`).
- **Feedback** (`feedback/api.py`):
  - `POST /requests/{id}/feedback {value}` and `POST /requests/{id}/flag {reason}`, both 204.
  - Owner role only (404 otherwise); a new vote replaces the last; the flag reason is redacted.
  - Both write rows and count in metrics.
- **Logs**: every JSON line inside a request carries `trace_id`, and the request log lines carry `request_id`. No question text is logged.
- **Failures**: any error in `/ask` or `/ask/stream`, not only gateway ones, now closes the request as `failed`. This resolves B's `TODO(session D)`.
- **Make targets**:
  - `make observability-secrets` writes the Langfuse and Grafana env files (mode 600) and appends `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `GRAFANA_DB_PASSWORD` to the main env file. Nothing is printed.
  - `make grafana-db-user` runs at the end of `make up`.
  - `check-env` requires the new variables and both side files at mode 600.
- **Tests**:
  - Unit: `tests/unit/test_{metrics,feedback,tracing,dashboards}.py`, with `test_logging.py` and `test_cost.py` extended.
  - Integration: `tests/integration/test_dashboard_views.py`.
- **Docs**:
  - ARCHITECTURE: build status, §2, §4, §5, §6, §8, §10, §11, §12.
  - ADR 0001 (reranker row), ADR 0002 (new dependencies), new ADR 0003, and the threshold section of `data/top20_questions.md`.
  - Screenshots in `docs/img/`.

## Verified

### Reranker, in the order asked

**1. Loaded once or per request.** Before the fix, the model was cached per process but loaded on the first request. Baseline (unchanged code, first calls after start), bge@30 per call, taken from the app's own progress bars. These are inflated: C's app was reranking on the same 8 CPUs at 500–900%.
```
$ docker compose logs app | grep -oE 'Batches: 100%.*1/1 \[[0-9:]+<' ...
00:41<  00:38<  00:52<  00:49<  00:44<  00:34<
```
After the fix, the first call after a restart does no loading; its rerank time matches a warm call:
```
[minilm15] first call (cold) rerank_ms=1688 wall_ms=6874
```

**2. Emulation**
```
$ docker container inspect d-observability-app-1 --format '{{.Name}} platform={{.Platform}}'
/d-observability-app-1 platform=linux
$ docker image inspect <image> --format '<image> {{.Os}}/{{.Architecture}}'
bas-assistant-app:local linux/arm64
ghcr.io/berriai/litellm-database:main-stable linux/arm64
pgvector/pgvector:pg16 linux/arm64
redis:7-alpine linux/arm64
prom/prometheus:v3.15.0 linux/arm64
grafana/grafana:13.2.2 linux/arm64
docker.langfuse.com/langfuse/langfuse:4 linux/arm64
docker.langfuse.com/langfuse/langfuse-worker:4 linux/arm64
postgres:17 linux/arm64
clickhouse/clickhouse-server:25.12 linux/arm64
cgr.dev/chainguard/minio linux/arm64
$ docker compose exec -T app sh -c 'uname -m; python -c "..."'
aarch64
machine aarch64
torch 2.14.0+cpu threads 8 interop 8
nproc 8
```

**3 and 4. 30 → 15, then MiniLM.** This A/B ran inside the app container on identical fused candidates (`scratchpad/rerank_ab.py`, same process, configs interleaved). It covered 22 queries: rows 1–18 as support, and rows 19–20 as support and engineer. A hit is the expected document in the top 5:
```
bge@30     th=0.5: expected doc in top5 15/17; hit and above threshold 15/17; abstains correctly 5/5
bge@15     th=0.5: expected doc in top5 15/17; hit and above threshold 15/17; abstains correctly 5/5
minilm@15  th=0.5: expected doc in top5 16/17; hit and above threshold 16/17; abstains correctly 3/5
minilm@15  th=0.8: expected doc in top5 16/17; hit and above threshold 16/17; abstains correctly 4/5
bge@30 n 22 min 31563 median 58792.5 max 150423      (ms, under C's contention)
bge@15 n 4 min 23110 median 29310.5 max 31967
minilm@15 n 22 min 3239 median 5787.0 max 17043
```
bge@15 was still far over 3 s, so the switch was made. MiniLM did not lose the expected document on any row: it gains row 12, and row 11 misses in every configuration. The stop condition (MiniLM losing more than 2 rows) did not trigger. The cost is one retrieval-level abstain, row 19 as support, which now reaches the answer model (ADR 0003).

**MiniLM@15 through the real endpoint** (`POST /search`, 20 golden rows × support/engineer). This ran before Langfuse was up; C's app was idle in 11 of 12 CPU samples, and the 6.9 s max is the one sample where C was at 620%:
```
$ python bench_search.py http://localhost:8001 minilm15
[minilm15] first call (cold) rerank_ms=1688 wall_ms=6874
[minilm15] warm n=39 rerank_ms p50=979 p95=2177 max=6932
[minilm15] correct 37/40
  miss row 11 support  abstained=True top=None top_doc=None
  miss row 11 engineer abstained=False top=0.8624401092529297 top_doc=DAC-633PoE
  miss row 19 support  abstained=False top=0.9532022476196289 top_doc=eZFC 424R4 24
```
**The same benchmark with this whole stack up** (Langfuse's ClickHouse steady at about one core) and C's evals at 500–700% for the second half. The 8 GB Docker VM's swap was full (1024/1024 MB). The reranker meets its budget, but this shared host does not (Known gaps):
```
[minilm15_fullstack] warm n=39 rerank_ms p50=5280 p95=13303 max=30412
[minilm15_fullstack] correct 37/40
```

### Stack

**make up** (with the port override), then compose ps:
```
$ make up HOST_URLS="POSTGRES_HOST=localhost POSTGRES_PORT=5434 LITELLM_BASE_URL=http://localhost:4001"
check-env: OK
docker compose up -d --build --wait
 ...
 Container d-observability-langfuse-web-1 Healthy
 Container d-observability-prometheus-1 Healthy
 Container d-observability-migrate-1 Exited
 Container d-observability-langfuse-clickhouse-1 Healthy
 Container d-observability-grafana-1 Healthy
 Container d-observability-app-1 Healthy
make litellm-keys
{"ts": "2026-09-27T10:50:15", "level": "INFO", "logger": "__main__", "message": "updated virtual key dev to $5.0/month"}
{"ts": "2026-09-27T10:50:15", "level": "INFO", "logger": "__main__", "message": "updated virtual key service to $2.0/month"}
make grafana-db-user
grafana-db-user: OK

$ docker compose ps -a
d-observability-app-1	Up 2 minutes (healthy)	127.0.0.1:8001->8000/tcp
d-observability-grafana-1	Up 2 minutes (healthy)	127.0.0.1:3000->3000/tcp
d-observability-langfuse-clickhouse-1	Up 54 minutes (healthy)	8123/tcp, 9000/tcp, 9009/tcp
d-observability-langfuse-minio-1	Up 54 minutes (healthy)
d-observability-langfuse-postgres-1	Up 54 minutes (healthy)	5432/tcp
d-observability-langfuse-redis-1	Up 54 minutes (healthy)	6379/tcp
d-observability-langfuse-web-1	Up 54 minutes (healthy)	127.0.0.1:3001->3000/tcp
d-observability-langfuse-worker-1	Up 54 minutes	3030/tcp
d-observability-litellm-1	Up About an hour (healthy)	127.0.0.1:4001->4000/tcp
d-observability-migrate-1	Exited (0) 2 minutes ago
d-observability-postgres-1	Up About an hour (healthy)	127.0.0.1:5434->5432/tcp
d-observability-prometheus-1	Up 54 minutes (healthy)	127.0.0.1:9090->9090/tcp
d-observability-redis-1	Up About an hour (healthy)	127.0.0.1:6380->6379/tcp

$ docker compose exec -T grafana sh -c 'env | cut -d= -f1 | grep -E "KEY|TOKEN|PASSWORD"'
GRAFANA_ADMIN_PASSWORD
GRAFANA_DB_PASSWORD
```

### Golden traffic through /ask

40 questions, cost $0.0492 per the receipts. This run started while ClickHouse and langfuse-web were warming up, which shows in the early rows:
```
$ python drive_ask.py http://localhost:8001
 1 support  answered  route=fast cache=False rerank_ms=4316 total_ms=8143 usd=0.000432
 1 engineer answered  route=fast cache=False rerank_ms=18178 total_ms=24009 usd=0.000438
 ...
14 support  answered  route=strong cache=False rerank_ms=2144 total_ms=7973 usd=0.006480
15 support  answered  route=strong cache=False rerank_ms=935 total_ms=6493 usd=0.006477
16 support  abstained route=fast cache=False rerank_ms=2569 total_ms=3609 usd=0.000028
17 support  abstained route=fast cache=False rerank_ms=808 total_ms=1999 usd=0.000028
18 support  abstained route=strong cache=False rerank_ms=665 total_ms=1609 usd=0.000030
19 support  abstained route=strong cache=False rerank_ms=738 total_ms=4909 usd=0.006416
19 engineer answered  route=strong cache=False rerank_ms=1460 total_ms=9408 usd=0.008546
20 support  abstained route=fast cache=False rerank_ms=554 total_ms=1644 usd=0.000031
20 engineer answered  route=fast cache=False rerank_ms=3209 total_ms=5534 usd=0.000423
requests=40 answered=21 usd=0.0492 total_ms p50=6186 p95=18712
rerank_ms n=39 p50=3179 p95=15988
```
Row 19 as support abstained end to end: the answer model said `answerable: false` about the eZFC passage, as ADR 0003 expected.

Rows 3, 8, 9 and 10 abstained even though MiniLM retrieved their documents. The answer model returned `answerable: false`, which B saw for rows 8 and 10 too (HANDOFF_B, "Retrieval precision"). Session C's golden eval owns this number.

### One /ask produces a full Langfuse trace

This is Langfuse 4.46, in "events_only" mode: the v1 `/api/public/traces` endpoint returns 404 and `/api/public/v2/observations` replaces it. The keys are read from the environment and nothing secret is printed:
```
$ python langfuse_trace.py http://localhost:3001
trace 1dade22f4787ed9ead6cc3430dda0342  session=ac433b11-c669-498e-a820-6d78f15a4b39  user=engineer
  url: http://localhost:3001/project/bas-assistant/traces/1dade22f4787ed9ead6cc3430dda0342
  SPAN       POST /ask          5.563s
    SPAN       node route         0.707s  {'route': 'fast'}
      GENERATION llm fast           0.702s  model=gpt-4o-mini in=140 out=16 usd=3.06e-05
    SPAN       node retrieve      3.486s  {'retrieved_count': 5, 'rerank_ms': 3209, 'retrieval_ms': 21}
      GENERATION llm embed          0.184s  model=text-embedding-3-small in=13 out=0 usd=2.6e-07
      SPAN       retrieval.search   0.021s
      SPAN       retrieval.rerank   3.209s  {'attributes.rerank.top_score': 0.9715079665184021, 'attributes.rerank.pairs': 15}
    SPAN       node answer        1.309s  {'attempts': 1}
      GENERATION llm fast           1.298s  model=gpt-4o-mini in=2328 out=71 usd=0.0003918
    SPAN       node validate      0.001s  {'validation_errors_count': 0}
```
A generation's full record also shows `costDetails {'total': 0.00019275}`, `usageDetails {'input': 957, 'output': 82, 'total': 1039}` and `model gpt-4o-mini`. Session id = thread id and user id = role were confirmed on the root observation.

**Screenshot: Jason takes it.** The Langfuse UI needs a login, which headless Chrome cannot do. Log in at http://localhost:3001 as `admin@bas.local` with `LANGFUSE_INIT_USER_PASSWORD` from `~/.bas-assistant-langfuse.env`, open the trace URL above, and save the screenshot as `docs/img/langfuse-trace.png`.

### Grafana: both dashboards with data, the embed, the role boundary

```
$ curl -s localhost:3000/grafana/api/search   # anonymous
   bas-budget | Budget | /grafana/d/bas-budget/budget
   bas-quality | Quality & adoption | /grafana/d/bas-quality/quality-and-adoption
$ curl -sI "localhost:3000/grafana/d/bas-budget/budget?orgId=1&kiosk" | grep -iE "^HTTP|x-frame-options"
HTTP/1.1 200 OK
$ anonymous POST /grafana/api/ds/query (Postgres data source):
 SELECT * FROM dash_spend_today
   {'spend_usd': 0.08790992, 'cap_usd': 3, 'pct_of_cap': 2.9}
 SELECT * FROM dash_flags_weekly
   {'week': 1789948800000, 'answered': 29, 'flagged': 3, 'flagged_pct': 10.3}
 SELECT thread_id FROM dash_questions
  ERROR: db query error: ERROR: permission denied for view dash_questions (SQLSTATE 42501)
 SELECT question_redacted FROM requests
  ERROR: db query error: ERROR: permission denied for table requests (SQLSTATE 42501)
 SELECT pg_sleep(8)
  ERROR: db query error: ERROR: canceling statement due to statement timeout (SQLSTATE 57014)
$ curl -s localhost:3000/grafana/api/prometheus/grafana/api/v1/rules
   API error rate above 5% | inactive | ok
   p95 answer latency above 8 s | inactive | ok
   Daily spend at 50% of the cap | inactive | ok
   Daily spend at 80% of the cap | inactive | ok
   Daily spend at 100% of the cap | inactive | ok
$ (Prometheus through Grafana) up{job="bas-assistant"}
   [[1790528321258], [1]]
```
Screenshots taken by headless Chrome after the golden traffic: `docs/img/grafana-budget.png` and `docs/img/grafana-quality.png`. The rerank panel shows B's bge rows at 15–18 s next to this session's hours.

**Embed**: there is no `X-Frame-Options` header (above), and `docs/img/grafana-iframe-test.png` shows both iframes loading Grafana's own boot screen, where a blocked frame would show the browser's refusal page. The headless capture ends before Grafana finishes rendering inside the frames. **A full visual check in a real browser is left to Jason**: open `deploy/grafana/iframe-test.html`.

### Tests

```
$ make lint
uv run ruff check src/ tests/ .claude/hooks/
All checks passed!
uv run ruff format --check src/ tests/ .claude/hooks/
99 files already formatted
uv run mypy src/ tests/ .claude/hooks/
Success: no issues found in 99 source files

$ make test
........................................................................ [ 36%]
........................................................................ [ 73%]
.....................................................                    [100%]
197 passed, 33 deselected in 32.95s
```

**make test-int**, run as its three commands against D's Postgres on 5434, because the target hardcodes C's 5433:
```
$ POSTGRES_HOST=localhost POSTGRES_PORT=5434 POSTGRES_DB=bas_test uv run alembic downgrade 0003 && ... upgrade head
INFO  [alembic.runtime.migration] Running downgrade 0004 -> 0003, Grafana: views behind every Postgres panel, a read-only role for them, budget rows.
INFO  [alembic.runtime.migration] Running upgrade 0003 -> 0004, Grafana: views behind every Postgres panel, a read-only role for them, budget rows.
$ ... uv run alembic check
No new upgrade operations detected.
$ ... REDIS_URL=redis://localhost:6380/1 uv run pytest -m integration
.............................                                            [100%]
29 passed, 201 deselected in 37.37s
```

### Reviewer

The first pass found 11 blocking issues, all fixed:
1. **`dash_questions` exposed ids.** It gave request, thread and user ids to anonymous Grafana viewers, enough to read other visitors' history through the API. It is no longer granted; an integration test asserts permission denied.
2. **No limits on the public SQL surface.** Fixed with the connection limit of 5, a 5 s `statement_timeout` and TEMP revoked from PUBLIC; Grafana uses at most 4 connections. Tested.
3. **Grafana had the whole env file**, vendor keys included. It now reads only its two passwords (`~/.bas-assistant-grafana.env`).
4. **User agent and client IP went to Langfuse.** A `server_request_hook` now blanks them. Tested.
5. **Flag and feedback percentages were wrong.** A request flagged twice counted twice, and non-answers counted in the numerators. Now each answered question counts once. Tested on real Postgres.
6. **`sync_daily_cap` was untested.** Unit test added.
7. **`configure_tracing` was untested and set the global provider itself.** It is now a pure `langfuse_provider()`, tested with and without keys; `main` sets the global.
8. **`Any` without a reason.** Reason added.
9. **ARCHITECTURE was stale** ("top-30", "tracing (D)" deferred). Fixed.
10. **B's `TODO(session D)`.** Non-gateway errors now close the request as `failed`. Tested.
11. **This handoff did not exist yet.** Written.

Non-blocking items also fixed:
- Tracer shutdown moved into `finally`.
- `failed=state.decision == "failed"` in the validation metric.
- Numeric span attributes are no longer turned into strings.
- The local import in `test_logging` moved to the top.
- New tests for stream tracing, the gate-resumed event, and a crash counted as `failed`.
- The span exporter is cleared on teardown.

Documented instead of fixed:
- The error-rate alert also fires on the daily-cap 503.
- `bas_requests_total` counts a request's first close only.

Left as they are: Langfuse under a compose profile, pinned Langfuse images, and moving `current_user` out of `agent/api.py` (Known gaps and Merge notes).

## Deferred

- **Alert contact point** (email or webhook): alerts show only on Grafana's alerting page. `TODO(session E)` in `rules.yaml`.
- **Langfuse on the droplet**: drop order #2; E decides. `TODO(session E)` in `deploy/langfuse/compose.yml`.
- **The tool-call metric**: the only tool is the ticket, counted by `bas_tickets_total{status}`.
- **The validation-failure-rate alert**: the counter and its panel exist.
- **The per-request ($0.10) and hourly-spike cost alerts** from ARCHITECTURE §6.
- **A Langfuse UI screenshot** (needs a login; Jason, see above) and a full in-browser render of `iframe-test.html`.
- **An uncontended bge@15 latency figure**: C's reranker was busy whenever I tried. ADR 0003 infers it from the halving and marks it as inferred.

## Known gaps

Each has a matching `TODO` in the source.

- **Shared-host latency** (`deploy/langfuse/compose.yml`): with C's stack, D's full stack and Langfuse on one 8-CPU / 8 GB Docker VM (swap full), MiniLM rerank p95 was 13–16 s against 2.2 s on a quiet host. ClickHouse alone used about one core while idle. On the droplet, the reranker will compete with whatever else runs there; Langfuse is the candidate to leave off.
- **Cold start** (`Dockerfile`): the image ships without `.pyc` files, so a start on a loaded host spent 4 minutes importing torch and transformers before uvicorn logged (container started 17:12:48, "Started server process" at 17:17:05). The first golden-traffic request hit that window and was dropped. `UV_COMPILE_BYTECODE=1` is the fix.
- **Grafana password race** (`Makefile`, `grafana-db-user`): Grafana starts before `make grafana-db-user` gives `grafana_reader` its password, so the alert evaluations in the first minute after a fresh `make up` fail on the login. They recover on their own.
- **`rerank_threshold` 0.8 was tuned on 20 rows** (`settings.py`, `TODO(session C)`).
- **Flag reasons are regex-redacted, not Presidio** (`feedback/api.py`, `TODO(session C)`).
- **Langfuse images float** (`:4`, `postgres:17`, `redis:7-alpine`, chainguard minio). Version 4.46.0 ran here (same TODO as above).
- **`/metrics` is on the app port**: E's Caddy must not route it, or Langfuse, publicly without auth (ARCHITECTURE §8).

## Merge notes

- **Alembic**: one new revision, `0004` (down_revision `0003`), so `alembic heads` stays at 1 unless C also adds a revision; in that case, rebase C's onto 0004. It creates:
  - 15 views and the `grafana_reader` role (cluster-wide, NOLOGIN until `make grafana-db-user`).
  - `ALTER ROLE` limits.
  - `REVOKE TEMP ON DATABASE <current> FROM PUBLIC`.
  - Two `budgets` rows.
  No table changes. `alembic check` is clean.
- **`eval_runs.scores` for C**: `dash_eval_latest` reads `scores->'overall'` when it is an object, else the top-level numeric keys. Write `{"overall": {"faithfulness": 0.9, ...}, "by_category": {...}}` and the Quality dashboard's "Latest evaluation scores" table fills itself.
- **New env vars**:
  - Main file: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `GRAFANA_DB_PASSWORD`, now required by `check-env`.
  - Side files: `~/.bas-assistant-langfuse.env` and `~/.bas-assistant-grafana.env`, both mode 600.
  - All of this is created by `make observability-secrets`, which I ran once. Optional setting: `LANGFUSE_HOST` (default `http://langfuse-web:3000`).
  - Compose now fails without the two side files, so run `make observability-secrets` before the first `make up` after merging.
- **Defaults changed**: `rerank_model` is now `cross-encoder/ms-marco-MiniLM-L-6-v2` (about 90 MB; downloaded to `model_cache` on first start), `rerank_threshold` 0.8, `CORPUS_VERSION` "2".
- **Dependencies**: `prometheus-client`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http` and `opentelemetry-instrumentation-fastapi`, with lines in ADR 0002. For `uv.lock`, run `uv lock`; never hand-merge.
- **Predictable conflicts with C** (both sessions edit these):
  - `agent/turn.py`: `question_redacted` is computed once in `open_turn` and feeds both `open_request` and the trace input. Keep that single variable when Presidio lands, so the trace gets the Presidio form. There are also the trace and metric calls in `open_turn`, `_respond` and `close_turn`, and `fail_turn` now takes a `reason`.
  - `agent/api.py`: the second `except Exception` in `/ask` and `/ask/stream`, and the trace lines in `/approve`.
  - `tests/unit/conftest.py` (the table list), `tests/graph_fakes.py` (`FakeRetriever.crash`), the Makefile, `docker-compose.yml`, `settings.py` and ARCHITECTURE.
- **Shared image tag**: every worktree's compose builds `bas-assistant-app:local`, so parallel sessions overwrite each other's image. My first build here did; D's own tag now comes from the uncommitted override. `make up` always builds, so this only bites a bare `docker compose up`. After merging, rebuild before trusting `:local`.
- **Docker Desktop 4.64.0 crashed** at 09:42 PDT with an internal panic, during my `docker tag` commands, and came back on its own about 5 minutes later with all volumes intact. If it happens again: Quit and relaunch. Never "Reset to factory defaults", which wipes the corpus volume.
- **Data**: D's stack ran on copies of B's volumes (`b-graph_pgdata`, `b-graph_model_cache`, copied into `d-observability_*`) and B's `data/raw`. Its Postgres holds B's requests plus this session's.
