# HANDOFF — session E: web app, deploy, How I built this

Branch `e-ship`, worktree `../bas-assistant-wt/e-ship`, from `main` at `14e81ba`. Live at
https://bas.jasonkhaings.com (a DigitalOcean droplet: Ubuntu 24.04, 2 vCPU, 4 GB RAM plus
2 GB swap, x86_64). DNS is a Route 53 A record with no proxy, added by Jason.

The local stack ran as `COMPOSE_PROJECT_NAME=bas-assistant` from this worktree, reusing main's
ingested `pgdata`. Only one stack ran at a time.

## Built

**Web app** (`web/`; ARCHITECTURE §11):
- Stack: Vite, React 19, strict TypeScript, Tailwind v4. The client is `openapi-fetch` over
  `src/api/schema.d.ts`, generated from `app.openapi()` (`npm run gen:api`).
- Top bar:
  - "View as" role switch (`X-Demo-Role`), with "roles come from SSO in production".
  - Budget chip from `GET /budget`.
  - Count of documents visible to the role.
  - Daily-cap banner on 503 `daily_budget_reached`.
- Chat:
  - Threads per role.
  - `POST /ask/stream` read with `fetch` and `eventsource-parser`: node steps, then the answer.
  - Citation cards (document, page, link, snippet; PDF links open at `#page=N`).
  - Three-way feedback, flag-with-reason, and "Show cost" (the receipt).
  - Paused-ticket callout.
- Approvals: admin token asked once and kept in React state only; list, approve, deny.
- Dashboards: both Grafana boards in same-origin kiosk iframes, with the caption from the plan.
- Evals: golden pass rate, RAGAS by category, red-team cases, and a paragraph per metric.
- How I built this: long-form page from the live run's numbers.
- Vitest and Testing Library tests with a stubbed `fetch`.
- FastAPI serves `web/dist` at `/`, mounted after every API route (`main.create_app`). The
  Dockerfile's `web` stage builds it.
- The UI uses hash routes and the API stays at root paths. This deviates from SESSIONS.md's
  `/api`; the typed client's paths then match the schema 1:1.

**Backend:**
- `GET /budget` → `{spent_usd, cap_usd, resets_at}` (`cost/api.py`).
- Answer-cache key with a corpus version read from the documents table:
  `db/corpus.current_corpus_version` gives `"{CORPUS_VERSION}.{count}.{max(ingested_at)}"`.
  - `AppRuntime.read_corpus_version` is a callable, because ingest runs in its own process.
  - `open_turn` reads it once per first question and keeps the key on `OpenTurn`, so
    `close_turn` stores under the same key.
  - This resolves the hotfix's `TODO(session E)`: stale abstains from an empty corpus.
- The golden, live-graph and red-team suites and `eval/ragas_run.py` compute and record the same
  version.
- `APP_URL` env override in `tests/eval/conftest.py`, so the golden set can run against the
  public URL.
- `bas_http_requests_total` counts only responses from API routes; static files would dilute the
  5xx-share alert.
- Tried and reverted (constraint 4): at most two passages per document in the final five.
  Evidence under Verified.

**Deploy** (`deploy/`, `docker-compose.prod.yml`; ARCHITECTURE §12):
- `setup_server.sh`:
  - Docker CE and the compose plugin, ufw 22/80/443, unattended upgrades, a 2 GB swap file.
  - `/etc/bas-assistant.env` (600): every secret generated except the three vendor keys, which
    Jason pasted.
  - Symlinks `/opt/bas-assistant/.env` and `/root/.bas-assistant.env` → it.
- `docker-compose.prod.yml`:
  - Services: app, migrate, Postgres, Redis (with a volume), LiteLLM, Prometheus, Grafana, Caddy.
    No Langfuse (constraint 1).
  - Only Caddy publishes 80 and 443; the rest bind to 127.0.0.1.
  - Grafana gets only its two passwords and its `root_url`, by interpolation.
  - A fixed subnet, with `FORWARDED_ALLOW_IPS` set to it, so the per-IP limit keys on visitors.
  - Log caps as in dev.
- `Caddyfile`: auto-TLS; `/metrics*` and `/grafana/metrics*` → 404; `/grafana*` → Grafana;
  everything else → the app. HSTS, nosniff, and `frame-ancestors 'self'`.
- `deploy.sh <ssh-target> [ref]`:
  - Runs on the laptop and ships `git archive <ref>` plus `data/raw`.
  - `release.sh` on the droplet builds, migrates, and sets the `grafana_reader` password before
    Grafana starts (resolves the Makefile TODO for prod).
  - It then starts the stack, registers the LiteLLM keys, and writes `REVISION`.
  - With an empty corpus it stops before Caddy (constraint 7). Otherwise it starts Caddy and
    smoke-tests `/healthz` and one `/ask` over HTTPS.
- Langfuse services are behind the compose profile `langfuse`: off by default, locally as well.
- Dockerfile:
  - A `web` stage on node 24-slim, pinned by digest.
  - `UV_COMPILE_BYTECODE=1`, which resolves D's cold-start TODO.

**CI**: the same single job, adding `actions/setup-node` with an npm cache, then `npm ci`,
`npm test` and `npm run build` in `web/`. No LLM calls, pull_request only.

**Docs**:
- README: what it is, architecture, run locally, numbers, what it does badly, deferred, and the
  runbook (Route 53).
- ARCHITECTURE: build status, stack line, §4, §6, §8, §11, §12, §13.
- ADR 0002: a web (npm) table.
- `docs/security-keys.md`: prod key table and rotation. `restart` does not re-read env files, and
  the vendor keys live in LiteLLM.

## Verified

All output below is pasted from this session. Long outputs are trimmed to the relevant lines,
never paraphrased.

### Constraint 8: the droplet before deploying (read-only check)

```
$ ssh root@<droplet> 'uname -m; lsb_release -ds; nproc; free -h; swapon --show; df -h /; which docker || echo "docker: none"'
x86_64
Ubuntu 24.04.4 LTS
2
               total        used        free      shared  buff/cache   available
Mem:           3.8Gi       456Mi       2.9Gi       4.0Mi       744Mi       3.4Gi
Swap:             0B          0B          0B
/dev/vda1        77G  1.9G   75G   3% /
docker: none
```

### setup_server.sh

```
$ ssh root@<droplet> 'bash -s' < deploy/setup_server.sh
...
setup_server: OK
Docker version 29.8.1, build 4a63305
Docker Compose version v5.5.1
NAME      TYPE SIZE USED PRIO
/swapfile file   2G   0B   -2
$ ssh root@<droplet> 'ufw status | tail -6; stat -c "%a %U %n" /etc/bas-assistant.env; ls -l /opt/bas-assistant/.env /root/.bas-assistant.env; grep -c "^[A-Z_]*=$" /etc/bas-assistant.env'
80/tcp                     ALLOW       Anywhere
443/tcp                    ALLOW       Anywhere
OpenSSH (v6)               ALLOW       Anywhere (v6)
...
600 root /etc/bas-assistant.env
lrwxrwxrwx 1 root root 22 Sep 27 22:29 /opt/bas-assistant/.env -> /etc/bas-assistant.env
lrwxrwxrwx 1 root root 22 Sep 27 22:29 /root/.bas-assistant.env -> /etc/bas-assistant.env
3
```
Jason then pasted the three vendor keys himself.

### Constraint 7: stack up, `make ingest`, then the link

The first `deploy.sh` (f80a4ae) exited 0 right after the migrations: `docker compose run --rm
migrate` read the rest of the script, which ssh was feeding through stdin. The droplet half became
`deploy/release.sh` (1fb0b0d), with no stdin for any docker command. The second run stopped before
Caddy, as designed:
```
$ deploy/deploy.sh root@<droplet> 1fb0b0d
 Container bas-assistant-app-1 Healthy
{"ts": "2026-09-27T22:44:05", ... "message": "created virtual key dev with $5.0/month"}
{"ts": "2026-09-27T22:44:05", ... "message": "created virtual key service with $2.0/month"}
release: 1fb0b0d is up without Caddy, because the corpus is empty.
release: run 'make ingest' in /opt/bas-assistant, then deploy again to open the link.
```

**Ingest on the 4 GB droplet.**
- The first `make ingest` ran inside the app container, beside the running app. It stalled after 12
  of 70 PDFs, with RAM and swap full:
  ```
  $ ssh root@<droplet> 'grep -c "Processing document" /root/ingest.log; free -h | sed -n 2,3p'
  12
  Mem:           3.8Gi       3.1Gi       213Mi        13Mi       899Mi       788Mi
  Swap:          2.0Gi       2.0Gi        18Mi
  $ ssh root@<droplet> 'docker stats --no-stream ...; ps -eo pid,rss,comm,args --sort=-rss | head -3'
  bas-assistant-app-1 2.433GiB / 3.824GiB 137.65%
    PID   RSS COMMAND         COMMAND
  16637 2504924 python        python -m bas_assistant.ingest
  ```
- I stopped it. The planned fallback was to truncate the partial corpus and restore the corpus
  dumped from the local stack. **The permission classifier denied the truncate on the prod
  database**, so I did not pursue it.
- Instead the ingest resumed with the app stopped, in a one-off container
  (`docker compose stop app`, then
  `docker compose run --rm --no-deps -T app python -m bas_assistant.ingest`). It is idempotent:
  the 11 committed documents were skipped by hash.
  ```
  ingest complete: ingested=101 updated=0 skipped=11 failed=0 documents_by_type={'pdf': 59, 'page': 42} chunks_by_type={'pdf': 822, 'page': 439} parents=1230 chunks=1261 parse_quality={'docling': 59, 'html': 42} embed_tokens=72279 embed_usd=0.0014455800000000000274 elapsed_s=1241.9
  ```
- Totals match the local corpus exactly. `make ingest` with the app up then skipped everything,
  before the link opened:
  ```
  $ ssh root@<droplet> 'cd /opt/bas-assistant && docker compose exec -T postgres psql -U bas_assistant -d bas_assistant -At -c "select count(*) || '"' documents (pdf '"' || count(*) filter (where source_type = '"'pdf'"') || '"', page '"' || count(*) filter (where source_type = '"'page'"') || '"')'"' from documents" -c "select count(*) || '"' parents'"' from parents" -c "select count(*) || '"' chunks, '"' || count(embedding) || '"' with embedding'"' from chunks"'
  112 documents (pdf 70, page 42)
  1459 parents
  1502 chunks, 1502 with embedding
  $ COMPOSE_PROJECT_NAME=bas-assistant docker compose exec -T postgres psql -U bas_assistant -d bas_assistant -At -c "select count(*) || ' documents (pdf ' || ...)" ...     # local, same queries
  112 documents (pdf 70, page 42)
  1459 parents
  1502 chunks
  $ ssh root@<droplet> 'cd /opt/bas-assistant && docker compose up -d --wait app && time make ingest'
   Container bas-assistant-app-1 Healthy
  {"ts": "2026-09-27T23:21:13", ... "message": "ingest complete: ingested=0 updated=0 skipped=112 failed=0 ... embed_usd=0 elapsed_s=81.7"}
  real	1m33.460s
  ```
- Eight discovered PDF URLs return 403 from the vendor's site and are skipped, the same on the
  laptop, so neither corpus has them (for example `eZV-enteliZONE-VAV-Controller-Catalog-Sheet-eZV-440.pdf`).

### The link opens over TLS (deploy 9d2fd6e, then the final deploy 9524680)

```
$ curl -sv https://bas.jasonkhaings.com/healthz
* SSL connection using TLSv1.3 / AEAD-CHACHA20-POLY1305-SHA256 / [blank] / UNDEF
*  subject: CN=bas.jasonkhaings.com
*  expire date: Dec 26 22:28:10 2026 GMT
*  issuer: C=US; O=Let's Encrypt; CN=YE2
< HTTP/2 200
{"status":"ok"}
$ deploy/deploy.sh root@<droplet> 9524680
{"status":"ok"}
smoke /ask: answered 1 citations, cache_hit True
release: 9524680 is live at https://bas.jasonkhaings.com
$ ssh root@<droplet> 'cd /opt/bas-assistant && cat REVISION && docker compose ps --format "{{.Service}}: {{.Status}}"'
9524680
app: Up 40 seconds (healthy)
caddy: Up 20 minutes
grafana: Up 20 minutes (healthy)
litellm: Up 6 minutes (healthy)
postgres: Up 6 minutes (healthy)
prometheus: Up 21 minutes (healthy)
redis: Up About an hour (healthy)
```
The first opening's smoke `curl` ran before Caddy had the certificate and failed silently. The
certificate came a moment later (ts 1790551603 = 23:26:43Z):
```
$ ssh root@<droplet> 'cd /opt/bas-assistant && docker compose logs caddy | grep -m1 "certificate obtained successfully"'
caddy-1  | {"level":"info","ts":1790551603.259111,"logger":"tls.obtain","msg":"certificate obtained successfully","identifier":"bas.jasonkhaings.com","issuer":"acme-v02.api.letsencrypt.org-directory"}
``` `release.sh` now retries both smoke calls (c32c8db), and
the final deploy above passed on its first run.

### Acceptance: answers with citations over TLS

```
$ curl -s https://bas.jasonkhaings.com/ask -H 'Content-Type: application/json' -H 'X-Demo-Role: support' -d '{"question":"How many inputs and outputs does the eZNT-T331 network thermostat have?"}' | tee live_ask.json | python3 -c 'import json,sys; r=json.load(sys.stdin); print("decision:", r["decision"], "| route:", r["route"], "| model:", r["model"], "| cache_hit:", r["cache_hit"]); print("answer:", r["answer"]); [print("citation:", c["document_title"], "p.", c["page"], c["source_url"]) for c in r["citations"]]; print("request_id:", r["request_id"])'
decision: answered | route: fast | model: gpt-4o-mini | cache_hit: False
answer: The eZNT-T331 network thermostat has 3 universal inputs and 3 analog outputs, along with 1 binary output.
citation: eZNT-T331 p. 1 https://deltacontrols.com/wp-content/uploads/eZNT-T331_Catalog_Sheet.pdf
request_id: 34256cd6-7913-4228-b0b6-6014351753b5
```

### Acceptance: Show cost works

```
$ curl -s https://bas.jasonkhaings.com/requests/34256cd6-7913-4228-b0b6-6014351753b5/receipt | python3 -c 'import json,sys; r=json.load(sys.stdin); print({k: r[k] for k in ("route","model","input_tokens","output_tokens","usd","retrieval_ms","rerank_ms","model_ms","total_ms","cache_hit")}); [print("  call:", c["stage"], c["model"], c["input_tokens"], "/", c["output_tokens"], "usd", c["usd"], c["latency_ms"], "ms") for c in r["calls"]]'
{'route': 'fast', 'model': 'gpt-4o-mini', 'input_tokens': 1759, 'output_tokens': 104, 'usd': 0.00032417, 'retrieval_ms': 95, 'rerank_ms': 1739, 'model_ms': 4969, 'total_ms': 6909, 'cache_hit': False}
  call: router gpt-4o-mini 385 / 31 usd 7.635e-05 3471 ms
  call: embed text-embedding-3-small 16 / 0 usd 3.2e-07 569 ms
  call: answer gpt-4o-mini 1358 / 73 usd 0.0002475 929 ms
```
In the UI, headless Chrome over CDP asked a fresh question on the live site and opened "Show cost":
`docs/img/live-chat.png`. It shows the node path, the answer, the Red5-PLUS-1180 p. 1 citation
card, the feedback and flag controls, a $0.000348 receipt with three calls, the budget chip, "110
documents visible", and the footer.

### Acceptance: the role switch changes the visible documents

```
$ for role in support engineer admin; do printf '%s: ' $role; curl -s https://bas.jasonkhaings.com/documents -H "X-Demo-Role: $role" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))'; done
support: 110
engineer: 112
admin: 112
```
The Vitest role-switch test asserts that the next request carries `X-Demo-Role: engineer` and that
the count changes.

### Acceptance: approve with the token files a ticket

The first attempt, as engineer, abstained at retrieval (under the 0.96 threshold), so no ticket was
drafted (Known gaps). A question grounded in a document section pauses at the gate:
```
$ curl -s https://bas.jasonkhaings.com/ask -H 'Content-Type: application/json' -H 'X-Demo-Role: engineer' -d '{"question":"The eZNS on site 14 has a cracked housing. Please open a support ticket."}' > live_ticket.json; python3 -c 'import json; r=json.load(open("live_ticket.json")); print("decision:", r["decision"], "| approval_required:", r["approval_required"], "| ticket_id:", r["ticket_id"], "| thread_id:", r["thread_id"]); print("answer:", r["answer"][:200])'
decision: abstained | approval_required: False | ticket_id: None | thread_id: bd04632c-9228-4603-81c3-f00b422780c0
answer: I couldn't find this in the documentation. I searched for: eZNS support. Try naming the product model, or ask about a spec, protocol or wiring detail.
$ curl -s https://bas.jasonkhaings.com/ask -H 'Content-Type: application/json' -H 'X-Demo-Role: engineer' -d '{"question":"What is the power requirement for the eBM-800 I/O module? Ours on site 14 gets 24 VAC from the eBCON-2 backplane but still will not power up, please open a support ticket."}' > live_ticket.json; python3 -c '<same formatter, plus notes and citations>'
decision: paused | approval_required: True | ticket_id: f70ea70e-95e5-47ac-9906-2265a87aac31 | thread_id: f48e24ea-748d-4329-bd5e-ff87b2664313 | notes: []
answer: The eBM-800 requires 24 VAC/VDC, 50/60 Hz at 5 VA. Its power is supplied through the backplane from an eBX or eBCON-2, not from a direct external supply.
citation: eBM-800 p. 2
$ T=f48e24ea-748d-4329-bd5e-ff87b2664313; curl -s -w "  HTTP %{http_code}\n" https://bas.jasonkhaings.com/approve -H 'Content-Type: application/json' -H 'X-Demo-Role: admin' -d "{\"thread_id\":\"$T\",\"approve\":true}"
{"detail":"admin token required"}  HTTP 401
$ ssh root@<droplet> "bash -s -- $T" < approve_live.sh      # script in the appendix; the token never leaves the droplet
{"thread_id":"f48e24ea-748d-4329-bd5e-ff87b2664313","ticket_id":"f70ea70e-95e5-47ac-9906-2265a87aac31","status":"filed"}  HTTP 200
$ ssh root@<droplet> 'cd /opt/bas-assistant && docker compose exec -T postgres psql -U bas_assistant -d bas_assistant -c "select t.id, t.status, t.draft->>'"'title'"' as title, u.role as approver from tickets t left join users u on u.id = t.approver_id order by t.created_at desc limit 1" -c "select action, actor, created_at::time(0) from audit where action like '"'ticket%'"' or action = '"'approve_refused'"' order by created_at desc limit 4"'
                  id                  | status |                    title                     | approver
 f70ea70e-95e5-47ac-9906-2265a87aac31 | filed  | eBM-800 I/O Module Not Powering Up – Site 14 | admin
     action      |                actor                 | created_at
 ticket_approved | 8f47a20a-2d15-4035-8ef0-7a0f868239b5 | 23:28:26
 ticket_filed    | agent                                | 23:28:26
 ticket_proposed | engineer                             | 23:28:01
```

### Acceptance: the Dashboards tab shows both Grafana boards live

```
$ B=https://bas.jasonkhaings.com; for p in /metrics /grafana/metrics "/grafana/d/bas-budget/budget?orgId=1&kiosk" "/grafana/d/bas-quality/quality-and-adoption?orgId=1&kiosk" / /docs; do printf '%-60s %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code} %{content_type}' "$B$p")"; done
/metrics                                                     404
/grafana/metrics                                             404
/grafana/d/bas-budget/budget?orgId=1&kiosk                   200 text/html; charset=UTF-8
/grafana/d/bas-quality/quality-and-adoption?orgId=1&kiosk    200 text/html; charset=UTF-8
/                                                            200 text/html; charset=utf-8
$ curl -sI https://bas.jasonkhaings.com/ | grep -iE "strict-transport|content-security|x-content-type"
content-security-policy: frame-ancestors 'self'
strict-transport-security: max-age=31536000
x-content-type-options: nosniff
```
`docs/img/live-dashboards.png` is the live Dashboards tab with both boards rendered in their
iframes. Budget shows spend today $0.0747 at 2.50% of the cap; Quality shows the latest evaluation
scores (faithfulness 0.734).

### Per-visitor rate limit behind Caddy (`FORWARDED_ALLOW_IPS`)

```
$ ssh root@<droplet> "cd /opt/bas-assistant && docker compose exec -T redis redis-cli --scan --pattern 'ratelimit:*'"
ratelimit:<droplet public IP>
ratelimit:<laptop public IP>
```
Both addresses are masked here. The limiter keys on real client addresses, the laptop and the
droplet itself, never on Caddy's compose-network address.

Only Caddy is reachable from outside. Docker-published ports bypass ufw, so the evidence is what
listens:
```
$ ssh root@<droplet> 'ss -tlnp' | awk 'NR==1 || /docker-proxy|sshd/'      # process column trimmed
State  Recv-Q Send-Q Local Address:Port Peer Address:Port
LISTEN 0      4096       127.0.0.1:5433      0.0.0.0:*
LISTEN 0      4096         0.0.0.0:22        0.0.0.0:*
LISTEN 0      4096       127.0.0.1:8000      0.0.0.0:*
LISTEN 0      4096         0.0.0.0:80        0.0.0.0:*
LISTEN 0      4096       127.0.0.1:4000      0.0.0.0:*
LISTEN 0      4096         0.0.0.0:443       0.0.0.0:*
LISTEN 0      4096       127.0.0.1:6379      0.0.0.0:*
LISTEN 0      4096            [::]:22           [::]:*
LISTEN 0      4096            [::]:80           [::]:*
LISTEN 0      4096            [::]:443          [::]:*
$ ssh root@<droplet> 'cat /etc/apt/apt.conf.d/20auto-upgrades; systemctl is-enabled unattended-upgrades; df -h / | tail -1'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
enabled
/dev/vda1        77G   34G   44G  44% /
```

### Acceptance: the Evals tab shows the latest run. Live golden set, RAGAS and red team (constraint 6)

Run on the droplet, where the secrets are. The red team ran against the stack; the golden set ran
against the public URL through Caddy:
```
== allowance keys (prod counters, not cleared):
allowance:6c592454-48fb-4a30-ad3e-9f212cc7f651:2026-09-27 = 1
allowance:5010cf62-c552-4029-aa68-4d3350c5ac3b:2026-09-27 = 2
== make redteam start 23:28:55Z
6 passed, 330 deselected in 61.30s (0:01:01)
== make redteam exit=0 end 23:30:07Z
== 61 s later 23:31:08Z
== make eval (APP_URL=https://bas.jasonkhaings.com) start 23:31:08Z
26 passed, 310 deselected in 161.34s (0:02:41)
{"ts": "2026-09-27T23:35:06", ... "message": "eval run 772e1799-f067-4002-97e6-ede9bface4a3: {\"passed\":22,\"total\":22,\"rate\":1.0}"}
== make eval exit=0 end 23:35:08Z
```
`eval/results/latest.md` (committed) is this run:
```
Corpus version `2.112.2026-09-27T23:17:56.018010+00:00`, prompt version `a2d7b390625a`. Cost $0.0529 (answers $0.0220, RAGAS judge $0.0309).
## Golden pass rate: 22/22 (100%)
| Category | n | Faithfulness | Answer relevancy | Context precision | Context recall |
| compatibility | 3 | 1.000 | 0.824 | 0.983 | 1.000 |
| engineer-only | 2 | 0.528 | 0.982 | 0.500 | 1.000 |
| ordering | 3 | 1.000 | 0.922 | 0.889 | 1.000 |
| protocol | 3 | 0.111 | 0.811 | 0.750 | 1.000 |
| spec | 3 | 0.889 | 0.907 | 0.722 | 1.000 |
| wiring-power | 3 | 0.806 | 1.000 | 1.000 | 1.000 |
| overall | 17 | 0.734 | 0.903 | 0.825 | 1.000 |
```
The numbers in the README and on the How-I-built-this page come from the prod DB over the live
eval window, 23:31:00Z to 23:35:10Z. That window holds the golden set plus B's live-graph checks
from the same `make eval`, which is why it has 25 uncached requests. The SQL is `numbers.sh` in
the appendix.
```
$ ssh root@<droplet> "bash -s -- 2026-09-27T23:31:00Z 2026-09-27T23:35:10Z" < numbers.sh
== cost per request by route and decision (golden window, cache hits excluded)
 route  | decision  | n  | median_usd | mean_usd | max_usd
 fast   | abstained |  3 |   0.000073 | 0.000074 | 0.000076
 fast   | answered  | 16 |   0.000310 | 0.000326 | 0.000496
 strong | abstained |  3 |   0.000077 | 0.000076 | 0.000077
 strong | answered  |  3 |   0.008927 | 0.008749 | 0.009557
== answer latency (answered, not cached), seconds
 n  | p50_s | p95_s
 19 |   6.0 |   9.5
== rerank_ms (answered and abstained, not cached)
 n  | p50_ms | p95_ms
 25 |   2932 | 4091.6
== eval_runs
  kind   |     created_at      | cost_usd |                  golden                  | rt_passed | rt_total
 golden  | 2026-09-27 23:35:06 |   0.0529 | {"rate": 1.0, "total": 22, "passed": 22} |           |
 redteam | 2026-09-27 23:30:03 |   0.0006 |                                          | 6         | 6
```
`docs/img/live-evals.png` is the live Evals tab. It shows golden 22/22, the RAGAS table with
protocol 0.111 marked low, and red team 6/6.

### Acceptance: the daily cap trips at $0.01 and is restored

```
$ ssh root@<droplet> 'bash -s -- 0.01' < set_cap.sh      # 23:38:26Z
DAILY_USD_CAP=0.01
 Container bas-assistant-app-1 Healthy
{"spent_usd":0.07470287,"cap_usd":0.01,"resets_at":"2026-09-28T00:00:00Z"}
HTTP/2 503
retry-after: 1212
{"detail":{"reason":"daily_budget_reached","message":"The demo has reached today's spending cap and is paused.","resets_at":"2026-09-28T00:00:00+00:00"}}
$ ssh root@<droplet> 'bash -s -- 3' < set_cap.sh
DAILY_USD_CAP=3
 Container bas-assistant-app-1 Healthy
{"spent_usd":0.07470287,"cap_usd":3.0,"resets_at":"2026-09-28T00:00:00Z"}
HTTP/2 200
{"answer":"enteliVAULT supports the Advanced Operator Workstation (B-AWS) BACnet device profile....","citations":[{"chunk_id":"2de7191e-...","document_title":"enteliVAULT","page":1, ...
```
`docs/img/live-daily-cap.png` shows the banner ("The demo's daily budget is used up. It resets at
5:00 PM PDT."), the red "$0.07 of $0.01" chip, and the API message under the question.

### Constraint 3: corpus version in the cache key

```
$ uv run pytest -m unit tests/unit/test_cost.py -k abstain_cached_before_an_ingest -v
======================= 1 passed, 10 deselected in 0.70s =======================
$ POSTGRES_HOST=localhost POSTGRES_PORT=5433 POSTGRES_DB=bas_test REDIS_URL=redis://localhost:6379/1 uv run pytest -m integration tests/integration/test_pg_retrieval.py -k corpus_version -v     # env file sourced as make test-int does
======================= 1 passed, 6 deselected in 8.88s ========================
```
- Unit: `test_an_abstain_cached_before_an_ingest_is_not_served_after_it` (test_cost.py).
- Integration: `test_corpus_version_moves_when_a_document_is_added_or_replaced` (test_pg_retrieval.py).
- Live: the results header reads `Corpus version 2.112.2026-09-27T23:17:56.018010+00:00` (droplet)
  and `2.112.2026-09-27T21:08:49.486098+00:00` (local). That is the retrieval part, 112 documents,
  and the latest ingest time.

### Constraint 4: passage cap experiment (reverted)

Baseline: protocol faithfulness 0.111 in both earlier local runs on this corpus (committed
`eval/results/latest.md` from 20:08Z, and main's uncommitted 21:15Z run):
```
$ git diff main -- eval/results/latest.md | grep -E "^-\| protocol"      # the 20:08Z run, replaced on this branch
-| protocol | 3 | 0.111 | 0.808 | 0.750 | 1.000 |
$ head -1 ../../bas-assistant/eval/results/latest.md; grep -E "^\| (protocol|engineer-only|overall) " ../../bas-assistant/eval/results/latest.md
# Golden set and RAGAS, 2026-09-27T21:15:20+00:00
| engineer-only | 2 | 0.700 | 0.979 | 0.500 | 0.500 |
| protocol | 3 | 0.111 | 0.827 | 0.750 | 1.000 |
| overall | 17 | 0.769 | 0.903 | 0.825 | 0.941 |
```
With the cap (local, 22:43Z; `eval/results/latest.md` of that run, saved aside):
```
Corpus version `2.112.2026-09-27T21:08:49.486098+00:00`, prompt version `a2d7b390625a`. Cost $0.0605 (answers $0.0284, RAGAS judge $0.0321).
## Golden pass rate: 22/22 (100%)
| engineer-only | 2 | 0.950 | 0.979 | 0.500 | 0.500 |
| protocol | 3 | 0.111 | 0.846 | 0.750 | 0.917 |
| overall | 17 | 0.759 | 0.911 | 0.821 | 0.926 |
```
No gain, so it was reverted (2d091f9). Why: in the baseline top five, no document holds more than
two places. Sibling products' sheets crowd them:
```
$ COMPOSE_PROJECT_NAME=bas-assistant docker compose exec -T postgres psql -U bas_assistant -d bas_assistant -c "
with latest as (
  select distinct on (question_redacted) id, question_redacted, created_at
  from requests
  where question_redacted in ('What BACnet device profile does the Red5-PLUS-1146 support?',
    'What BACnet device profile does enteliVAULT support?',
    'What communication ports does the eZNS network sensor have?')
    and decision = 'answered'
  order by question_redacted, created_at desc)
select left(l.question_redacted, 40) as question, rc.rank, round(rc.score::numeric, 4) as score, d.title, c.page, rc.used_in_answer as cited
from latest l join request_chunks rc on rc.request_id = l.id
join chunks c on c.id = rc.chunk_id join documents d on d.id = c.document_id
order by l.question_redacted, rc.rank;"       # before the cap run; enteliVAULT rows trimmed
 question                                  | rank | score  | title                                      | page | cited
 What BACnet device profile does the Red5  |    1 | 0.9993 | Red5-PLUS-1146                             |    1 | t
 What BACnet device profile does the Red5  |    2 | 0.9988 | Red5 EDGE 1146                             |    1 | f
 What BACnet device profile does the Red5  |    3 | 0.9973 | Red5-PLUS-1180                             |    1 | f
 What BACnet device profile does the Red5  |    4 | 0.9952 | Red5-PLUS-1146                             |    2 | f
 What BACnet device profile does the Red5  |    5 | 0.9946 | Red5 PLUS ROOM                             |    1 | f
 What communication ports does the eZNS n  |    1 | 0.9994 | eZFC 424R4 24                              |    2 | f
 What communication ports does the eZNS n  |    2 | 0.9992 | eZVP 440E                                  |    2 | f
 What communication ports does the eZNS n  |    3 | 0.9988 | eZV enteliZONE VAV Controller              |    2 | f
 What communication ports does the eZNS n  |    4 | 0.9967 | eZNS                                       |    2 | t
```
The passage texts RAGAS judges never name the product:
```
$ COMPOSE_PROJECT_NAME=bas-assistant docker compose exec -T postgres psql -U bas_assistant -d bas_assistant -At -c "
with latest as (select id from requests where question_redacted='What BACnet device profile does the Red5-PLUS-1146 support?' and decision='answered' order by created_at desc limit 1)
select rc.rank || ' [' || d.title || '] ' || left(replace(p.text, E'\n', ' '), 160) from latest l join request_chunks rc on rc.request_id=l.id join chunks c on c.id=rc.chunk_id join parents p on p.id=c.parent_id join documents d on d.id=c.document_id order by rc.rank;"      # first 3 rows
1 [Red5-PLUS-1146] ## Specifications  BACnet Device Profile BACnet Building Controller (B-BC)
2 [Red5 EDGE 1146] ## Specifications  BACnet Device Profile BACnet Building Controller (B-BC)
3 [Red5-PLUS-1180] ## Specifications  BACnet Device Profile BACnet Building Controller (B-BC)
```

### Constraints 5 and 6: local run (allowance cleared, 61 s gap)

```
== allowance keys before clear (22:38:40Z):
== allowance keys after clear: 0
== make redteam start 22:38:40Z
6 passed, 329 deselected in 29.13s
== make redteam exit=0 end 22:39:13Z
== 61 s later 22:40:14Z
== allowance keys before clear (22:40:14Z):
allowance:7a754b83-891d-4bd2-a37e-07f33210cdac:2026-09-27 = 6
== allowance keys after clear: 0
== make eval start 22:40:15Z
26 passed, 309 deselected in 134.67s (0:02:14)
## Golden pass rate: 22/22 (100%)
```
Support's 42/50 from the hotfix stack was already gone at the first clear. Dev Redis has no
volume, and the stack was recreated. Prod counters were fresh (1 and 2, from the acceptance calls
above).

### Local UI through the real backend, and GET /budget

```
$ curl -s localhost:8000/budget
{"spent_usd":0.07497384,"cap_usd":3.0,"resets_at":"2026-09-28T00:00:00Z"}
$ curl -s localhost:8000/ | head -c 400; echo; curl -s -o /dev/null -w "healthz %{http_code} %{content_type}\n" localhost:8000/healthz; curl -s -o /dev/null -w "asset %{http_code} %{content_type}\n" "localhost:8000$(curl -s localhost:8000/ | grep -oE '/assets/[^"]+\.js' | head -1)"
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta
      name="description"
      content="Portfolio demo: a support assistant that answers from public product documentation with page citations
healthz 200 application/json
asset 200 text/javascript; charset=utf-8
$ uv run python shoot.py "http://localhost:8000/#/chat" local-chat.png --ask "What is the power draw of the Red5-PLUS-1180?" --cost --wait 1      # page text, excerpt
answered
cached
route fast · model gpt-4o-mini

The power draw of the Red5-PLUS-1180 is 24 VDC (20 W max) or 24 VAC at 50 VA, with a maximum of 100 VA when fully loaded with internally powered triac outputs.

SOURCES
Red5-PLUS-1180
(opens in a new tab)
p. 1
...
Model
cache
Tokens
0 in / 0 out (0 cached)
Cost
$0.000000
...
Cache hit
yes
```
The same driver on the live site, for a question that is not in the golden set (Known gaps):
```
$ uv run python shoot.py "https://bas.jasonkhaings.com/#/chat" live-chat.png --ask "What is the power requirement of the eZNT-T331 thermostat?" --cost --wait 1      # excerpt
abstained
route fast · model gpt-4o-mini

I couldn't find this in the documentation. I searched for: eZNT-T331 thermostat. Try naming the product model, or ask about a spec, protocol or wiring detail.
```

### Tests, lint, build (final)

```
$ make lint
All checks passed!
127 files already formatted
Success: no issues found in 122 source files
$ make test
273 passed, 63 deselected, 8 warnings in 19.55s
$ make test-int
No new upgrade operations detected.
31 passed, 305 deselected in 15.96s
$ cd web && npm test
 Test Files  7 passed (7)
      Tests  26 passed (26)
$ cd web && npm run build
✓ built in 156ms
$ docker run --rm -e DOMAIN=bas.example.com -v "$PWD/deploy/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2 caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
Valid configuration
$ COMPOSE_PROJECT_NAME=bas-assistant docker compose ps --format '{{.Service}}: {{.Status}}'     # local
app: Up 51 minutes (healthy)
grafana: Up About an hour (healthy)
litellm: Up About an hour (healthy)
postgres: Up About an hour (healthy)
prometheus: Up About an hour (healthy)
redis: Up About an hour (healthy)
```
Web function and file sizes (a TypeScript AST script; nothing lints TS sizes in CI):
```
$ node measure.cjs web
max function length: 40 (limit 40); over limit: 0
max control-flow nesting: 2 (src/hooks/useTicketDecisions.ts:23 decide)
max file length: 221 (limit 300); over limit: 0
```
**CI: not run.** Its single job only runs on `pull_request`, and this session pushes the branch
without opening a PR. Each of its steps (gitleaks via the pre-commit hook, ruff, mypy,
`pytest -m unit`, `npm ci`, `npm test`, `npm run build`) was run locally above.

### Reviewer

First pass: 7 blocking issues, all fixed.
1. The How-I-built-this page was 337 lines, with one 291-line function. It is now one file per
   section, with the numbers in `run.ts`.
2. `useTickets` was over 40 lines: loading and decisions are split.
3. Twelve components were over 40 lines: split by meaning (for example `CurrentPage`,
   `TicketSection`, `ReceiptCalls`, `FlagForm`).
4. The feedback and flag controls had no tests: added.
5. The Evals page had no tests: added (shape guards, failures, fallback, low-score marker).
6. ARCHITECTURE said "21/22": updated to the live 22/22 run.
7. ARCHITECTURE §12 said Langfuse runs with `make up`: now says the `langfuse` profile.

Non-blocking items fixed:
- Static files are no longer counted in the HTTP metric; tested.
- Caddy 404s `/grafana/metrics` and sets `frame-ancestors 'self'`.
- `read_corpus_version` naming.
- `no_startup` made public.
- The integration test's extra engine is disposed.
- `TODO(session E)` tags relabelled `post-weekend`, with lines below.
- The node image is pinned by digest.
- The rollback caveat is in the script, README and ARCHITECTURE.
- The IP was removed from the deploy usage comment.
- Thread keys use `crypto.randomUUID()`, the SSE client uses `EventSourceParserStream`, and
  `isRecord` moved to `api/guards.ts`.
- The README `make test` comment is fixed.

Second pass: 4 blocking issues, all fixed.
1. Handoff commands were abbreviated: the exact commands are pasted, with the Content-Type header
   and the formatter pipes.
2. Output came from scripts that weren't shown: the scripts are in the appendix, and the corpus-count
   and diagnostic queries are pasted.
3. Known gaps lacked TODOs: every actionable gap now has a `TODO(post-weekend)`, and observations
   moved to Merge notes.
4. The paused-ticket callout had no test: added, along with a Dashboards iframe test.

Non-blocking items taken:
- Numbers are labelled "live eval run".
- The abstain cost reads "$0.00007 to $0.00008".
- The `run.ts` comment is corrected.
- "22 checks", not "22 questions".
- The vendor-key gap also names migrate and Postgres.
- `ss -tlnp` and the unattended-upgrades evidence are pasted.
- The p95 alert gap is added.
- The droplet address is masked.
- ARCHITECTURE: the tests bullet and the stale `embed` line are fixed.

Left as they are:
- The web build is skipped silently when `web/dist` is missing. It always exists in the image, and
  the smoke test loads `/`.
- `evalScores.ts` hand-types the score documents that OpenAPI declares as open objects. Typing
  `EvalRunOut.scores` in the API would generate them; post-weekend.

## Deferred

- Langfuse on the droplet (drop order #2, by Jason's constraint 1). No `/langfuse` route in Caddy.
- The How-I-built-this page and the Evals tab shipped as planned. Drop orders #1 and #3 were not
  needed.
- The settings.py vendor-key split: the app never reads the vendor keys, but removing the fields
  touches three test files. `TODO(post-weekend)` in `settings.py`. Vendor hard limits bound the
  blast radius.
- Grafana alert contact point: `TODO(post-weekend)` in `rules.yaml`.
- Langfuse image pins: `TODO(post-weekend)` in `deploy/langfuse/compose.yml`.
- Local `make up`: Grafana starts before the reader's password is set (prod does it in
  `release.sh`). `TODO(post-weekend)` in the Makefile.
- Repo public: Jason's step, after merging.

## Known gaps

Each has a matching `TODO(post-weekend)` in the file named.

- **Protocol faithfulness 0.111** (`eval/ragas_run.py`, `_contexts`). Part of it is measurement: the
  judge gets each parent's text without its document title, which the answer model sees, and these
  sections never name the product (Verified, constraint 4). Part is real crowding by sibling
  products' identical sections.
  - Next steps: judge the passages as the model saw them, and deduplicate identical sections
    across documents.
  - Stated on the How-I-built-this page and in the README.
- **The ticket gate needs a question that retrieves** (`settings.py`, `rerank_threshold`). At 0.96, a
  fault report that names no documented section abstains before the answer model, so no ticket
  is drafted (Verified: the cracked-housing question). A fault report grounded in a spec pauses at
  the gate as designed.
- **A cold ingest needs the app stopped on the 4 GB droplet** (`Makefile`, `ingest`). Docling reached
  2.5 GB beside the running app. The README runbook, "Re-index", gives the one-off container
  command.
- **Rollback** (`deploy/deploy.sh`): the tree is unpacked over the old one, so files a newer ref added
  stay, and migrations never run down.
- **The app, migrate and Postgres containers get the whole `/etc/bas-assistant.env`**, vendor keys
  and admin token included, though only LiteLLM needs the vendor keys (`settings.py`,
  `docker-compose.prod.yml`).
- **The p95 latency alert (8 s) sits below the droplet's measured p95 (9.5 s)**, so it fires under
  normal load (`deploy/grafana/provisioning/alerting/rules.yaml`).
- **No alert contact point** (the same file): alerts show only on Grafana's alerting page.
- **Local `make up`** starts Grafana before `grafana-db-user` sets the reader's password (`Makefile`).
  Prod does it in `release.sh`.
- **Langfuse image tags are not pinned** (`deploy/langfuse/compose.yml`).
- **Claude prompt caching is inactive**: the system prompt is under the 1,024-token minimum
  (`config/litellm.yaml`, unchanged).
- **The web tests stub `fetch`**, and there is no browser end-to-end test in CI
  (`web/src/tests/setup.ts`). The live checks above used headless Chrome by hand.

## Merge notes

- No migrations, no new env vars for the app, no new Python dependencies.
  - New npm dependencies: `web/package.json`, ADR 0002.
  - On the droplet, `DOMAIN` and `COMPOSE_FILE` live in `/etc/bas-assistant.env`, written by
    `setup_server.sh`.
- `AppRuntime.corpus_version: str` became `read_corpus_version: Callable[[], str]`. Any code that
  builds an `AppRuntime` needs the new field.
- `tests/graph_fakes._no_startup` is now `no_startup`.
- Langfuse is off by default. Run `COMPOSE_PROFILES=langfuse make up` to get traces locally.
- The local `~/.npm` cache has root-owned files, so `npm install` fails with EACCES. Fix it with
  `sudo chown -R 501:20 ~/.npm`. This session used a scratchpad cache instead.
- `eval/results/latest.md` is the live droplet run.
- **Redeploy after merging.** The droplet runs `9524680`. The final commit adds this handoff and the
  review fixes: TODO comments, two web tests, doc wording. None of them changes runtime behaviour.
  Run `deploy/deploy.sh root@<droplet> <main ref>` so the droplet runs a ref on main.
- **The droplet also holds the dev dependencies** (`/opt/bas-assistant/.venv`, for the on-droplet
  evals). They are not in the image. Disk: 34 GB used of 77 GB.
- Observations, not code gaps:
  - Engineer-only faithfulness was 0.528 live and 0.950 locally an hour earlier. With n = 2 and a
    gpt-4o-mini judge, category scores move this much between runs.
  - "What is the power requirement of the eZNT-T331 thermostat?" abstained on the live site
    (Verified). I did not check whether its catalog sheet states it.

## Appendix: helper scripts behind the pasted output

Scratchpad scripts, not in the repo. Each was run as shown in Verified: droplet scripts through
`ssh root@<droplet> 'bash -s' < script`, the local ones from the worktree.

<details><summary><code>numbers.sh</code>: Droplet: cost per request, latency and eval runs over a time window (README and page numbers).</summary>

```bash
#!/usr/bin/env bash
# Runs on the droplet: the README / How-I-built-this numbers from the live golden run window.
# Usage: numbers.sh <start-ISO-UTC> <end-ISO-UTC>
set -euo pipefail
cd /opt/bas-assistant
docker compose exec -T postgres psql -U bas_assistant -d bas_assistant -v start="$1" -v stop="$2" <<'SQL'
\echo == cost per request by route and decision (golden window, cache hits excluded)
with per_request as (
  select r.id, r.route, r.decision, r.latency_ms, sum(u.usd) as usd, bool_or(u.cache_hit) as cached
  from requests r join usage u on u.request_id = r.id
  where r.created_at between :'start' and :'stop'
  group by r.id, r.route, r.decision, r.latency_ms
)
select route, decision, count(*) as n,
       round(percentile_cont(0.5) within group (order by usd)::numeric, 6) as median_usd,
       round(avg(usd)::numeric, 6) as mean_usd,
       round(max(usd)::numeric, 6) as max_usd
from per_request where not cached
group by route, decision order by route, decision;

\echo == answer latency (answered, not cached), seconds
with per_request as (
  select r.id, r.latency_ms, bool_or(u.cache_hit) as cached
  from requests r join usage u on u.request_id = r.id
  where r.created_at between :'start' and :'stop' and r.decision = 'answered'
  group by r.id, r.latency_ms
)
select count(*) as n,
       round((percentile_cont(0.5) within group (order by latency_ms) / 1000.0)::numeric, 1) as p50_s,
       round((percentile_cont(0.95) within group (order by latency_ms) / 1000.0)::numeric, 1) as p95_s
from per_request where not cached;

\echo == rerank_ms (answered and abstained, not cached)
select count(*) as n,
       percentile_cont(0.5) within group (order by rerank_ms) as p50_ms,
       percentile_cont(0.95) within group (order by rerank_ms) as p95_ms
from requests where created_at between :'start' and :'stop' and rerank_ms > 0;

\echo == eval_runs
select kind, created_at::timestamp(0), cost_usd, scores->'golden' as golden, scores->'passed' as rt_passed, scores->'total' as rt_total
from eval_runs order by created_at desc limit 3;

\echo == spend today
select round(sum(usd)::numeric, 4) as usd_today from usage where created_at >= date_trunc('day', now() at time zone 'utc') at time zone 'utc';
SQL
```

</details>

<details><summary><code>remote_evals.sh</code>: Droplet: prod allowance counters, `make redteam`, 61 s, then `make eval` against the public URL.</summary>

```bash
#!/usr/bin/env bash
# Runs on the droplet: red team, a 61 s gap, then the golden set + RAGAS against the public URL.
set -uo pipefail
export PATH=/root/.local/bin:$PATH
cd /opt/bas-assistant
echo "== allowance keys (prod counters, not cleared):"
docker compose exec -T redis redis-cli --scan --pattern 'allowance:*' </dev/null | while read -r key; do
  printf '%s = %s\n' "$key" "$(docker compose exec -T redis redis-cli get "$key" </dev/null)"
done
echo "== make redteam start $(date -u +%H:%M:%SZ)"
make redteam </dev/null
echo "== make redteam exit=$? end $(date -u +%H:%M:%SZ)"
sleep 61
echo "== 61 s later $(date -u +%H:%M:%SZ)"
echo "== make eval (APP_URL=https://bas.jasonkhaings.com) start $(date -u +%H:%M:%SZ)"
APP_URL=https://bas.jasonkhaings.com make eval </dev/null
echo "== make eval exit=$? end $(date -u +%H:%M:%SZ)"
```

</details>

<details><summary><code>local_evals.sh</code>: Laptop: clear the allowance keys, `make redteam`, 61 s, clear again, `make eval`.</summary>

```bash
#!/usr/bin/env bash
# Local eval sequence for session E: clear allowance counters, red team, 61 s gap, golden + RAGAS.
set -uo pipefail
cd /Users/jasonkhaings/Desktop/bas-assistant-wt/e-ship
export COMPOSE_PROJECT_NAME=bas-assistant

clear_allowances() {
  echo "== allowance keys before clear ($(date -u +%H:%M:%SZ)):"
  docker compose exec -T redis redis-cli --scan --pattern 'allowance:*' | while read -r key; do
    printf '%s = %s\n' "$key" "$(docker compose exec -T redis redis-cli get "$key")"
    docker compose exec -T redis redis-cli del "$key" >/dev/null
  done
  echo "== allowance keys after clear: $(docker compose exec -T redis redis-cli --scan --pattern 'allowance:*' | wc -l | tr -d ' ')"
}

clear_allowances
echo "== make redteam start $(date -u +%H:%M:%SZ)"
make redteam
echo "== make redteam exit=$? end $(date -u +%H:%M:%SZ)"
sleep 61
echo "== 61 s later $(date -u +%H:%M:%SZ)"
clear_allowances
echo "== make eval start $(date -u +%H:%M:%SZ)"
make eval
echo "== make eval exit=$? end $(date -u +%H:%M:%SZ)"
```

</details>

<details><summary><code>set_cap.sh</code>: Droplet: set `DAILY_USD_CAP`, recreate the app, probe `/budget` and `/ask`.</summary>

```bash
#!/usr/bin/env bash
# Runs on the droplet: set DAILY_USD_CAP, recreate the app so it reads it, then probe /budget and /ask.
# Usage: set_cap.sh <usd>
set -euo pipefail
cd /opt/bas-assistant
sed -i "s/^DAILY_USD_CAP=.*/DAILY_USD_CAP=$1/" /etc/bas-assistant.env
grep '^DAILY_USD_CAP=' /etc/bas-assistant.env
docker compose up -d --wait app </dev/null 2>&1 | tail -1
curl -s "https://bas.jasonkhaings.com/budget"
echo
curl -s -D - -o /tmp/ask_body.json "https://bas.jasonkhaings.com/ask" \
  -H 'Content-Type: application/json' -H 'X-Demo-Role: support' \
  -d '{"question":"What BACnet device profile does enteliVAULT support?"}' | grep -iE '^HTTP|^retry-after'
cat /tmp/ask_body.json
echo
```

</details>

<details><summary><code>approve_live.sh</code>: Droplet: approve one paused thread with the admin token, which is never printed.</summary>

```bash
#!/usr/bin/env bash
# Runs on the droplet: approve one paused thread with the admin token from /etc/bas-assistant.env.
# The token goes only into the request header; nothing prints it.
set -euo pipefail
THREAD=$1
set -a; . /etc/bas-assistant.env; set +a
curl -s -w '  HTTP %{http_code}\n' "https://$DOMAIN/approve" \
  -H 'Content-Type: application/json' -H 'X-Demo-Role: admin' -H "X-Admin-Token: $ADMIN_TOKEN" \
  -d "{\"thread_id\":\"$THREAD\",\"approve\":true}"
```

</details>

<details><summary><code>shoot.py</code>: Laptop: headless Chrome over CDP. Opens the app, optionally asks and opens the receipt, screenshots the page, prints its text.</summary>

```python
"""Screenshot the web app with headless Chrome over CDP, optionally asking a question first.

usage: uv run python shoot.py URL OUT.png [--ask QUESTION] [--role ROLE] [--cost] [--wait S]
"""

import argparse
import asyncio
import base64
import json
import subprocess
import tempfile
import time
import urllib.request

import websockets

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9333

SET_VALUE = """
(el, value) => {
  const proto = el.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLTextAreaElement.prototype;
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
  el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', {bubbles: true}));
}
"""


class Page:
    def __init__(self, ws: websockets.ClientConnection) -> None:
        self.ws, self.next_id = ws, 0

    async def call(self, method: str, **params: object) -> dict:
        self.next_id += 1
        await self.ws.send(
            json.dumps({"id": self.next_id, "method": method, "params": params})
        )
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == self.next_id:
                return msg.get("result", {})

    async def js(self, expr: str) -> object:
        r = await self.call(
            "Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True
        )
        return r.get("result", {}).get("value")

    async def until(self, expr: str, timeout: float) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if await self.js(expr):
                return True
            await asyncio.sleep(0.5)
        return False


async def run(args: argparse.Namespace) -> None:
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json") as r:
        target = next(t for t in json.load(r) if t["type"] == "page")
    async with websockets.connect(
        target["webSocketDebuggerUrl"], max_size=50_000_000
    ) as ws:
        page = Page(ws)
        await page.call(
            "Emulation.setDeviceMetricsOverride",
            width=1280,
            height=1000,
            deviceScaleFactor=1,
            mobile=False,
        )
        await page.call("Page.navigate", url=args.url)
        await page.until("document.readyState === 'complete'", 30)
        await asyncio.sleep(2)
        if args.role:
            await page.js(
                f"({SET_VALUE})(document.querySelector('select'), {json.dumps(args.role)})"
            )
            await asyncio.sleep(2)
        if args.ask:
            await page.js(
                f"({SET_VALUE})(document.querySelector('textarea'), {json.dumps(args.ask)})"
            )
            await asyncio.sleep(0.5)
            await page.js(
                "document.querySelector('form button[type=submit], form button').click()"
            )
            done = "[...document.querySelectorAll('button')].some(b => b.textContent.trim() === 'Show cost') || document.body.innerText.includes('daily budget')"
            print("answer shown:", await page.until(done, 180))
            if args.cost:
                await page.js(
                    "[...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Show cost').click()"
                )
                print(
                    "receipt shown:",
                    await page.until(
                        "!!document.querySelector('[aria-label=\"Cost receipt\"]') && document.querySelector('[aria-label=\"Cost receipt\"]').textContent.includes('$')",
                        30,
                    ),
                )
        await asyncio.sleep(args.wait)
        height = await page.js("Math.max(document.body.scrollHeight, 1000)")
        await page.call(
            "Emulation.setDeviceMetricsOverride",
            width=1280,
            height=int(height),
            deviceScaleFactor=1,
            mobile=False,
        )
        await asyncio.sleep(1)
        shot = await page.call("Page.captureScreenshot", format="png")
        with open(args.out, "wb") as f:
            f.write(base64.b64decode(shot["data"]))
        print("saved", args.out, "height", height)
        text = await page.js(
            "document.querySelector('main') ? document.querySelector('main').innerText.slice(0, 1500) : document.body.innerText.slice(0, 1500)"
        )
        print(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("out")
    parser.add_argument("--ask")
    parser.add_argument("--role")
    parser.add_argument("--cost", action="store_true")
    parser.add_argument("--wait", type=float, default=2)
    args = parser.parse_args()
    profile = tempfile.mkdtemp(prefix="chrome-cdp-")
    chrome = subprocess.Popen(
        [
            CHROME,
            "--headless=new",
            f"--remote-debugging-port={PORT}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--hide-scrollbars",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(40):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version")
                break
            except OSError:
                time.sleep(0.25)
        asyncio.run(run(args))
    finally:
        chrome.terminate()


if __name__ == "__main__":
    main()
```

</details>
