# HANDOFF — hotfix/eval-on-main

`make eval` on main after the C and D merges failed in three ways. Every answerable golden row
abstained with citations `[]`. Row 20 got 429 for both roles. `eval/ragas_run.py` crashed with
`IndexError` on an empty sample list.

Root cause: main's compose stack (project `bas-assistant`) ran on a fresh `pgdata` volume, created
2026-09-27 20:37Z after the disk-full incident. Nobody had run `make ingest` against it, so
retrieval had nothing to search. Retrieval config was correct.
The 429 came from the same cause. With no corpus, each abstain took about 1 s, so 22 requests
arrived within 25 s against a limit of 20 a minute. In C, answers took several seconds each, so
the run never reached 20 in a minute. C had no localhost exemption: `guardrails/limits.py` there
is byte-identical to main's.

## Built

- Corpus restored in main's stack: `data/raw` seeded from `d-observability`'s crawl cache (113
  files, gitignored), then `make ingest`. Only `robots.txt` was fetched live.
- `src/bas_assistant/evals/pacing.py`: `pacing_hook(limit, window_s)`, an httpx request hook
  that sends at most `limit` requests in any trailing `window_s`. The first `limit` requests go
  out at once.
- `tests/eval/conftest.py`: one session-scoped client shared by `test_golden.py` and
  `test_live_graph.py`. It is paced to `Settings().ip_rate_limit` per `RATE_WINDOW` + 1 s, so
  the whole run shares one budget, as the app's limiter does.
- `tests/eval/test_golden.py`: stops with `pytest.exit` before asking anything when
  `GET /documents` (as engineer) is empty. It empties `golden-latest.jsonl` first, so RAGAS
  cannot score the previous run as this one.
- `eval/ragas_run.py`: exits 1 with a one-line message, instead of a traceback, when no golden
  row was answered. It writes no `eval_runs` row.
- `tests/unit/test_pacing.py`: requests up to the limit do not wait, and the next one waits for
  the window.
- `docs/ARCHITECTURE.md` §9 as-built: pacing, the empty-corpus stop, and RAGAS's no-answer exit.

Not built, by choice: a localhost exemption in the limiter. The app sees the dev host as
`172.22.0.1` (the compose network's gateway, below), not `127.0.0.1`. Behind Caddy, every
visitor shares one address until session E sets `FORWARDED_ALLOW_IPS`. An address exemption
could therefore exempt the whole public link.

## Verified

### Diagnosis 1: corpus in the running Postgres (before the fix)

```
$ docker compose exec -T postgres psql -U bas_assistant -d bas_assistant \
    -c "select count(*) as documents from documents" -c "select count(*) as parents from parents" \
    -c "select count(*) as chunks, count(embedding) as chunks_with_embedding from chunks" \
    -c "select id, vector_dims(embedding) as dims, embedding is not null as nonnull, (embedding::real[])[1:4] as head from chunks order by id limit 1"
 documents
-----------
         0
 parents
---------
       0
 chunks | chunks_with_embedding
--------+-----------------------
      0 |                     0
 id | dims | nonnull | head
----+------+---------+------
(0 rows)

$ docker volume inspect bas-assistant_pgdata --format '{{.Name}} created {{.CreatedAt}}'
bas-assistant_pgdata created 2026-09-27T20:37:14Z
```

### Diagnosis 2: POST /search for golden question 1 as support (before the fix)

```
$ curl -s -X POST localhost:8000/search -H 'X-Demo-Role: support' \
    -d '{"question":"How many inputs and outputs does the eZNT-T331 network thermostat have?"}'
abstained: True | citations: 0 | candidates: 0 | timings: {'embed_ms': 506, 'retrieval_ms': 58, 'rerank_ms': 0, 'total_ms': 565}

$ docker compose exec -T app python -c "...Settings(); load_reranker(...)"
rerank_threshold = 0.96
rerank_model = cross-encoder/ms-marco-MiniLM-L-6-v2
loaded CrossEncoder: cross-encoder/ms-marco-MiniLM-L-6-v2 | activation: Sigmoid
```

No candidates meant no rerank scores. The reranker was never called (`rerank_ms: 0`).

### Diagnosis 3: limits in effect (before the fix)

```
app env overrides: DAILY_USD_CAP=3 (no IP_RATE_LIMIT / USER_DAILY_QUESTIONS set -> defaults 20/min, 50/role/day)
$ docker compose exec -T redis redis-cli --scan --pattern 'ratelimit:*'
ratelimit:172.22.0.1
allowance:<engineer>:2026-09-27 = 1
allowance:<support>:2026-09-27 = 19
 action       | count | max
 decision     |    20 | 2026-09-27 20:42:09.06761+00
 rate_limited |     1 | 2026-09-27 20:42:09.07488+00
$ diff <(git -C ../bas-assistant-wt/c-guardrails show HEAD:src/bas_assistant/guardrails/limits.py) src/bas_assistant/guardrails/limits.py && echo "limits.py: C HEAD == main"
limits.py: C HEAD == main
```

### Fix: ingest into main's stack

```
$ cp -p ../bas-assistant-wt/d-observability/data/raw/* data/raw/ && ls data/raw | wc -l && du -sh data/raw && time make ingest
     113
 59M	data/raw
{"ts": "2026-09-27T21:08:49", "level": "INFO", "logger": "__main__", "message": "ingest complete: ingested=112 updated=0 skipped=0 failed=0 documents_by_type={'pdf': 70, 'page': 42} chunks_by_type={'pdf': 1063, 'page': 439} parents=1459 chunks=1502 parse_quality={'docling': 70, 'html': 42} embed_tokens=86660 embed_usd=0.0017332000000000000294 elapsed_s=1053.8"}
make ingest 2>&1  0.22s user 0.38s system 0% cpu 17:50.83 total
```

Diagnosis 1 again:

```
 documents
-----------
       112
 parents
---------
    1459
 chunks | chunks_with_embedding
--------+-----------------------
   1502 |                  1502
                  id                  | dims | nonnull |                       head
--------------------------------------+------+---------+---------------------------------------------------
 0029d4cb-d6c0-4382-a60f-b0d6587102ae | 1536 | t       | {-0.005405426,0.01940918,0.02619934,-0.024353027}
```

Diagnosis 2 again (golden question 1 as support, every candidate's rerank score):

```
threshold: 0.96 | abstained: False | citations: 5 | candidates: 20 | timings: {'embed_ms': 504, 'retrieval_ms': 150, 'rerank_ms': 2743, 'total_ms': 3450}
  0.9997  eZNT-T331 p1
  0.9996  eZNT Wi T331 p1
  0.9985  eZNT T304 p1
  0.9971  Eznt Wi p1
  0.9970  eZNT-T331 p1
  0.9929  eZNT-T331 p1
  0.8873  eZNT Wi T331 p1
  0.8388  eZNT-T331 p1
  0.6997  eZNT-T331 p1
  0.6826  eZNT Wi T331 p1
  0.6470  eZNT T304 p1
  0.5947  eZNT-T331 p2
  0.3921  Ezntw p1
  0.1932  eZNTW p1
  0.1810  eZNT-T331 p1
  0.1807  Eznt p1
  0.1768  eZNT-T331 p3
  0.1499  eZNT-T331 p2
  0.0550  eZNT-T331 p4
  0.0376  eZNT-T331 p4
citations:
  0.9997  eZNT-T331 p1  eZNT-T331_Catalog_Sheet.pdf
  0.9996  eZNT Wi T331 p1  eZNT-Wi-T331_Catalog_Sheet.pdf
  0.9985  eZNT T304 p1  eZNT-T304_Catalog_Sheet.pdf
  0.9971  Eznt Wi p1
  0.9970  eZNT-T331 p1  eZNT-T331_Catalog_Sheet.pdf
```

### ragas_run.py on the failed run's results (0 of 22 answered)

```
$ uv run python eval/ragas_run.py; echo "exit=$?"
ragas_run: none of the 22 results in golden-latest.jsonl was answered, so there is nothing to score and no eval_runs row is written.
exit=1
```

(RAGAS's own import-time `DeprecationWarning` lines trimmed; they were there before this change.)

### Lint, unit tests, stack

```
$ make lint
All checks passed!
127 files already formatted
Success: no issues found in 122 source files
$ make test
269 passed, 62 deselected, 8 warnings in 19.46s
$ docker compose ps --format '{{.Service}}: {{.Status}}'
app: Up 33 minutes (healthy)
grafana: Up 33 minutes (healthy)
langfuse-clickhouse: Up 34 minutes (healthy)
langfuse-minio: Up 34 minutes (healthy)
langfuse-postgres: Up 34 minutes (healthy)
langfuse-redis: Up 34 minutes (healthy)
langfuse-web: Up 33 minutes (healthy)
langfuse-worker: Up 33 minutes
litellm: Up 33 minutes (healthy)
postgres: Up 34 minutes (healthy)
prometheus: Up 34 minutes (healthy)
redis: Up 34 minutes (healthy)
$ curl -s localhost:8000/healthz
{"status":"ok"}
```

### make eval

Run after the push, as instructed. The result is in `eval/results/latest.md` and in the session
reply, not in this commit.

## Deferred

- None from this hotfix's scope.

## Known gaps

- A first ingest does not bump `CORPUS_VERSION`. Abstains cached while the corpus was empty
  keep being served for their 24 h TTL. On this stack, 18 such keys exist from the failed run.
  The golden run deletes its own keys before asking, so `make eval` is unaffected.
  `TODO(session E)` in `settings.py`: ingest before the link opens, or flush `answer:*`.

## Merge notes

- No migrations, no new env vars, no new dependencies.
- The new file `tests/eval/conftest.py` moves `APP_URL` and `TIMEOUT_S` out of
  `test_golden.py`, and `test_live_graph.py` loses its own `app` fixture. Session E conflicts
  only if it edits those lines.
- A fresh stack needs `make ingest` before `make eval`, and `make eval` now says so.
- The pacer sees only its own requests. Leave a minute between `make redteam` and `make eval`,
  because they share the host's one address at the limiter.
- The golden set plus `test_live_graph` uses 23 of support's 50 daily questions. Support had
  used 19 before this run, so a second `make eval` today would get `daily_allowance_used`.
