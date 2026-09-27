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
- **Defaults changed**: `rerank_model` is now `cross-encoder/ms-marco-MiniLM-L-6-v2` (about 90 MB; downloaded to `model_cache` on first start), `rerank_threshold` 0.8 (0.96 after the C merge, see Post-merge), `CORPUS_VERSION` "2".
- **Dependencies**: `prometheus-client`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http` and `opentelemetry-instrumentation-fastapi`, with lines in ADR 0002. For `uv.lock`, run `uv lock`; never hand-merge.
- **Predictable conflicts with C** (both sessions edit these):
  - `agent/turn.py`: `question_redacted` is computed once in `open_turn` and feeds both `open_request` and the trace input. Keep that single variable when Presidio lands, so the trace gets the Presidio form. There are also the trace and metric calls in `open_turn`, `_respond` and `close_turn`, and `fail_turn` now takes a `reason`.
  - `agent/api.py`: the second `except Exception` in `/ask` and `/ask/stream`, and the trace lines in `/approve`.
  - `tests/unit/conftest.py` (the table list), `tests/graph_fakes.py` (`FakeRetriever.crash`), the Makefile, `docker-compose.yml`, `settings.py` and ARCHITECTURE.
- **Shared image tag**: every worktree's compose builds `bas-assistant-app:local`, so parallel sessions overwrite each other's image. My first build here did; D's own tag now comes from the uncommitted override. `make up` always builds, so this only bites a bare `docker compose up`. After merging, rebuild before trusting `:local`.
- **Docker Desktop 4.64.0 crashed** at 09:42 PDT with an internal panic, during my `docker tag` commands, and came back on its own about 5 minutes later with all volumes intact. If it happens again: Quit and relaunch. Never "Reset to factory defaults", which wipes the corpus volume.
- **Data**: D's stack ran on copies of B's volumes (`b-graph_pgdata`, `b-graph_model_cache`, copied into `d-observability_*`) and B's `data/raw`. Its Postgres holds B's requests plus this session's.

## Post-merge

`origin/main` (with session C) was merged into `d-observability` as merge commit `ac5b51f`, followed by one fix commit. Nothing on `main` was touched. C's stack was stopped with your go-ahead (`docker compose stop` in `c-guardrails`; containers and volumes kept), so D ran on the **standard ports**, and every `make` target below ran unmodified.

### How the conflicts were resolved

13 files conflicted. The rule was: keep C's code and layout, then re-apply D's instrumentation on top.

- **C's moves kept**: `agent/validate.py` → `guardrails/output.py`, and `agent/prompts.py` → `agent/prompts/`.
- **Graph**: `screen` stays unwrapped (it takes state only). `route`, `refuse` and `retrieve` get node spans. The span fields gain `refusal` and `refusal_rail`; `refusal_reason` stays out, because it is the router's words about the question.
- **Turn**: the trace input is C's Presidio-redacted `question`, the same string as the requests row. C's `_audit_decision` calls stay beside D's logging.
- **Failures**: `fail_turn` keeps a reason on C's key-budget (429) and model-unavailable (503) paths, and D's catch-all still closes any other error as `failed`.
- **Other files**: `gateway.complete` keeps D's span around C's `parse_usage`. The pipeline keeps D's rerank span around C's title-aware `_rerank_text`. Settings keep C's `ip_rate_limit` and D's `corpus_version` "2". `main` gets C's evals router and D's instrumentation. `pyproject.toml` and ADR 0002 take both sides, and `uv.lock` was regenerated with `uv lock`.
- **Flag reasons**: Presidio now redacts them too, which resolves D's `TODO(session C)` in `feedback/api.py`.
- **Tests**: two D tests were changed to match C's behaviour: Presidio writes `<EMAIL_ADDRESS>`, and `/approve` needs `X-Demo-Role: admin`.

### Alembic

- C and D had both added revision id `0004`. A merge revision can't tell two revisions with the same id apart, so D's migration was renumbered: `0005_dashboards`, with `down_revision "0004"` on top of C's `0004_prompt_version`. There is one head.
- D's two databases were recorded at D's old `0004`. I ran that migration's downgrade SQL, stamped them `0003`, and upgraded to the new head:
```
$ uv run alembic heads
0005 (head)
== bas_assistant
INFO  [alembic.runtime.migration] Running upgrade 0003 -> 0004, Record which prompt version answered each request.
INFO  [alembic.runtime.migration] Running upgrade 0004 -> 0005, Grafana: views behind every Postgres panel, a read-only role for them, budget rows.
No new upgrade operations detected.
== bas_test
INFO  [alembic.runtime.migration] Running upgrade 0003 -> 0004, Record which prompt version answered each request.
INFO  [alembic.runtime.migration] Running upgrade 0004 -> 0005, Grafana: views behind every Postgres panel, a read-only role for them, budget rows.
No new upgrade operations detected.
```

### ClickHouse's 33 GB error log

**Cause.** The ClickHouse image logs at `trace` level to the console, as well as to files of up to 10 × 1000 MB each (its `config.xml`: `<level>trace</level>`, `<size>1000M</size>`, `<count>10</count>`, console by autodetection). Docker's `json-file` log had no cap. Once the Docker disk was full, every flush of ClickHouse's own telemetry tables failed every few seconds and logged a full stack trace, which kept the disk full. From the surviving error log:
```
2026.09.27 17:53:21.839638 [ 1441 ] {} <Error> void DB::SystemLog<DB::AsynchronousMetricLogElement>::flushImpl(...): Failed to flush system log system.asynchronous_metric_log
...
4. DB::MergeTreeData::reserveSpacePreferringTTLRules(...)
```

**Fix.**
- `deploy/langfuse/clickhouse.xml`, mounted into ClickHouse's `config.d`: level `warning`, files 2 × 50 MB, and the telemetry tables Langfuse never reads removed (`asynchronous_metric_log`, `metric_log`, `trace_log`, `text_log`, `processors_profile_log`, `query_metric_log`).
- Every one of the 13 compose services now has `logging: json-file`, `max-size: 50m`, `max-file: 2`.

After the fix, ClickHouse's container log held 7 lines, and it idled at about 5% CPU, down from about one core:
```
$ docker exec d-observability-langfuse-clickhouse-1 sh -c '<grep the preprocessed ClickHouse config>'
        <level>warning</level>
        <size>50M</size>
        <count>2</count>
telemetry tables still configured: 0
container log lines since start:        7
clickhouse log driver=json-file opts=map[max-file:2 max-size:50m]
app log driver=json-file opts=map[max-file:2 max-size:50m]
```

### Row 16: the refund question was refused

C's router returned a yes/no `is_off_topic`. Calling the real `classify()` 10 times on row 16 before the fix:
```
   7 refusal=None route=fast
   3 refusal=off_topic route=fast
```

**Fix** (`llm/router.py`, `prompts/router.md`):
- `is_off_topic` became `scope: on_topic | unclear | off_topic`.
- `unclear` is a question the company could be asked that names no product: a refund, an account, a policy. It goes to retrieve and abstains there. Only `off_topic` refuses.
- The model also ticked `is_injection` for "write me a poem" (in 2 of 3 runs), which would have shown the injection message. An `off_topic` scope now wins over that flag; real override phrasings are caught by `screen` first.
- Unit tests were added for both behaviours.

After, row 16 alone, 10 runs:
```
  10 refusal=None route=fast
```
Three questions, 3 runs each:
```
run 1: refusal=None      route=fast   "What is the refund policy if I'm not satisfied with my purch"
run 2: refusal=None      route=fast   "What is the refund policy if I'm not satisfied with my purch"
run 3: refusal=None      route=fast   "What is the refund policy if I'm not satisfied with my purch"
run 1: refusal=None      route=strong "Does Delta Controls' O3 platform integrate with a Honeywell "
run 2: refusal=None      route=strong "Does Delta Controls' O3 platform integrate with a Honeywell "
run 3: refusal=None      route=strong "Does Delta Controls' O3 platform integrate with a Honeywell "
run 1: refusal=off_topic route=fast   'Write me a poem about the ocean.'
run 2: refusal=off_topic route=fast   'Write me a poem about the ocean.'
run 3: refusal=off_topic route=fast   'Write me a poem about the ocean.'
```
End to end through `/ask`, 3 times, with Redis flushed before each so no run was a cache hit:
```
run 1: {'decision': 'abstained', 'route': 'fast', 'cache_hit': False} "I couldn't find this in the documentation. I searched for: refund policy. ..."
run 2: {'decision': 'abstained', 'route': 'fast', 'cache_hit': False} "I couldn't find this in the documentation. I searched for: refund policy. ..."
run 3: {'decision': 'abstained', 'route': 'fast', 'cache_hit': False} "I couldn't find this in the documentation. I searched for: refund policy. ..."
```

### Threshold: MiniLM with titles

This scan ran the app's own `retrieve()` in the container, with the threshold at 0, over every golden check:
```
answerable hits 17 / 17
answerable hit top scores [0.988, 0.9932, 0.9956, 0.9964, 0.9985, 0.9989, 0.9989, 0.9991, 0.9992, 0.9993, 0.9994, 0.9994, 0.9995, 0.9996, 0.9997, 0.9998, 0.9999]
must-abstain top scores [(0.0, 16, 'support'), (0.1381, 17, 'support'), (0.1675, 20, 'support'), (0.5049, 18, 'support'), (0.9442, 19, 'support')]
```
**`rerank_threshold` = 0.96.** It sits between 0.944 and 0.988, so every must-abstain check abstains at retrieval. The margins are narrow; that caveat is in the settings comment, ADR 0003 and `data/top20_questions.md`.

**First `make eval` (15 candidates): 21 / 22.**
- Row 13 abstained. The answer model got 5 enteliWEB passages without the browser list.
- The `## Client Browser` chunk, which MiniLM scores 1.000, fuses at rank 18, so 15 candidates cut it. C passed row 13 because main still had 30.
- Timed in one process, interleaved, over the 22 checks:
  ```
  15 pairs: n 44 p50 1336 p95 2637 max 3140
  20 pairs: n 44 p50 2045 p95 3419 max 3429
  ```
- **You chose 20.** The threshold scan at 20 gave the same split (answerable 0.988–1.000, must-abstain up to 0.944). Rerank p95 of 3.4 s is recorded in ADR 0003 as about 0.4 s over the 3 s rerank budget.

### make lint, test, test-int (final code)
```
$ make lint
All checks passed!
124 files already formatted
Success: no issues found in 119 source files
$ make test
267 passed, 62 deselected, 8 warnings in 20.23s
$ make test-int
No new upgrade operations detected.
30 passed, 299 deselected in 17.62s
```

### make up (standard ports), then compose ps
```
 Container d-observability-app-1 Healthy
make litellm-keys
{"ts": "2026-09-27T12:59:08", "level": "INFO", "logger": "__main__", "message": "updated virtual key dev to $5.0/month"}
{"ts": "2026-09-27T12:59:08", "level": "INFO", "logger": "__main__", "message": "updated virtual key service to $2.0/month"}
make grafana-db-user
grafana-db-user: OK

d-observability-app-1	Up 15 minutes (healthy)	127.0.0.1:8000->8000/tcp
d-observability-grafana-1	Up 35 minutes (healthy)	127.0.0.1:3000->3000/tcp
d-observability-langfuse-clickhouse-1	Up 35 minutes (healthy)	8123/tcp, 9000/tcp, 9009/tcp
d-observability-langfuse-minio-1	Up 35 minutes (healthy)
d-observability-langfuse-postgres-1	Up 35 minutes (healthy)	5432/tcp
d-observability-langfuse-redis-1	Up 35 minutes (healthy)	6379/tcp
d-observability-langfuse-web-1	Up 35 minutes (healthy)	127.0.0.1:3001->3000/tcp
d-observability-langfuse-worker-1	Up 35 minutes	3030/tcp
d-observability-litellm-1	Up 35 minutes (healthy)	127.0.0.1:4000->4000/tcp
d-observability-migrate-1	Exited (0) 15 minutes ago
d-observability-postgres-1	Up 35 minutes (healthy)	127.0.0.1:5433->5432/tcp
d-observability-prometheus-1	Up 35 minutes (healthy)	127.0.0.1:9090->9090/tcp
d-observability-redis-1	Up 35 minutes (healthy)	127.0.0.1:6379->6379/tcp
```

### make ingest
Idempotent: every source was unchanged, so nothing was embedded and it cost $0. One PDF not in the cache returned 403 and was skipped.
```
{"ts": "2026-09-27T19:47:49", "level": "INFO", "logger": "__main__", "message": "ingest complete: ingested=0 updated=0 skipped=112 failed=0 documents_by_type={} chunks_by_type={} parents=0 chunks=0 parse_quality={} embed_tokens=0 embed_usd=0 elapsed_s=84.4"}
```

### make eval (final: MiniLM, titles, 20 candidates, threshold 0.96)
```
26 passed, 303 deselected in 151.46s (0:02:31)
eval run 2bbf99ab-fe1d-4d05-8f86-6fd5f3599f39: {"passed":22,"total":22,"rate":1.0}

Corpus version `2`, prompt version `a2d7b390625a`. Cost $0.0610 (answers $0.0304, RAGAS judge $0.0307).
## Golden pass rate: 22/22 (100%)
(every row: pass; rows 16, 17, 18, 19 support and 20 support: abstained)

| Category | n | Faithfulness | Answer relevancy | Context precision | Context recall |
|---|---|---|---|---|---|
| compatibility | 3 | 1.000 | 0.806 | 0.983 | 1.000 |
| engineer-only | 2 | 0.688 | 0.979 | 0.500 | 0.500 |
| ordering | 3 | 0.889 | 0.898 | 0.889 | 1.000 |
| protocol | 3 | 0.111 | 0.808 | 0.750 | 1.000 |
| spec | 3 | 1.000 | 0.907 | 0.712 | 1.000 |
| wiring-power | 3 | 0.889 | 1.000 | 1.000 | 1.000 |
| overall | 17 | 0.767 | 0.895 | 0.824 | 0.941 |
```
The first run (15 candidates, row 13 failing) scored protocol faithfulness 0.667 and overall 0.885 / 0.887 / 0.818 / 0.922. The protocol drop to 0.111 is on 3 rows, judged by the `fast` alias, in a run where those rows' golden checks all passed. I have not established whether it is the judge's variance or a real change in the passages; it should be re-run before any number goes into the README (session E).

### make redteam
```
$ make redteam
6 passed, 323 deselected in 25.36s
exit=0
```

### Langfuse trace and screenshots
```
$ python langfuse_trace.py http://localhost:3001
trace 3abddc10ed2087887e4690bef2db8948  session=1e104abf-2773-4aff-a6bb-73c309e36bb9  user=support
  url: http://localhost:3001/project/bas-assistant/traces/3abddc10ed2087887e4690bef2db8948
  SPAN       POST /ask          5.993s
    SPAN       node route         1.091s  {'route': 'fast'}
      GENERATION llm fast           1.084s  model=gpt-4o-mini in=383 out=31 usd=7.605e-05
    SPAN       node retrieve      3.271s  {'retrieved_count': 5, 'rerank_ms': 2831, 'retrieval_ms': 57}
      GENERATION llm embed          0.371s  model=text-embedding-3-small in=14 out=0 usd=2.8e-07
      SPAN       retrieval.search   0.058s
      SPAN       retrieval.rerank   2.831s  {'attributes.rerank.top_score': 0.9992583394050598, 'attributes.rerank.pairs': 20}
    SPAN       node answer        1.481s  {'attempts': 1}
      GENERATION llm fast           1.476s  model=gpt-4o-mini in=1016 out=98 usd=0.000211199999
    SPAN       node validate      0.015s  {'validation_errors_count': 0}
```
- **`docs/img/langfuse-trace.png`**: taken with Playwright driving the installed Chrome, logged in as `admin@bas.local`. It shows the tree, the redacted question as input, the validated answer as output, cost, tokens, session, user, and the blanked client fields.
  - Langfuse v4's events-only mode takes a trace's input and output from its root observation, so the root span now also sets `langfuse.observation.input` / `output`. The first screenshot had shown `null`.
- **`docs/img/grafana-iframe-test.png`**: now fully rendered. Playwright waited for both iframes, where the earlier headless capture stopped at Grafana's boot screen.
- **`grafana-budget.png` and `grafana-quality.png`**: retaken after the post-merge traffic.

### Disk

The Docker VM had 12 GB free at the end (58.4 GB disk, 43.3 GB used), mostly images and BuildKit cache from today's rebuilds. `docker builder prune` would reclaim some, but the cache is shared with the other worktrees, so that is your call.

### Post-merge gaps

- **Rerank p95 3.4 s** is over the 3 s rerank budget (your choice of 20 candidates, recorded in ADR 0003). End-to-end p95 of 8 s is the target that matters.
- **RAGAS faithfulness for protocol** dropped to 0.111 on 3 rows (above). Re-run before publishing numbers.
- **`rerank_threshold` 0.96 has narrow margins** (`settings.py` comment; ADR 0003).
- **`make up` warm-up**: the app is healthy only after the model loads and Python imports torch and transformers; `UV_COMPILE_BYTECODE` is still E's `TODO` in the `Dockerfile`.
- **Merge note for E**: compose now needs `deploy/langfuse/clickhouse.xml` beside its compose file. The prod compose (E) should copy the logging caps.
