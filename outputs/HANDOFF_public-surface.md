# Handoff: chore/public-surface

Branch `chore/public-surface` off `main` (`74bd6bd`), Oct 5 2026.

The public link showed more than a visitor needs: the interactive API docs and the OpenAPI
schema listed every route and the admin header, and How I built this linked to `#/admin`, which
the README says is not linked. This branch closes both, checks that the admin endpoints reject a
missing and a wrong token, and takes private build context out of tracked docs and comments.

## Built

- **API docs switch.** `settings.ApiDocsSettings` reads `API_DOCS` (default off) and
  `main.create_app(api_docs=...)` sets `docs_url` and `openapi_url` from it.
  - `docker-compose.yml` sets `API_DOCS: "true"`, so `/docs` and `/openapi.json` stay on locally.
  - `docker-compose.prod.yml` does not set it, so the droplet serves neither.
  - `/redoc` was already off everywhere and stays off.
  - It is a class of its own because `Settings` requires every secret and the app object is
    built at import time, where unit tests and `npm run gen:api` have none.
- **No public link to `#/admin`.** In `web/src/pages/howIBuiltThis/AQuestionArrives.tsx` the
  Orchestration section's "See it: #/admin" link is now a code link to
  `src/bas_assistant/agent/graph.py`. The route and `AdminPage` are unchanged.
- **Admin token check fails closed.** `agent/api.require_admin` now rejects every request when
  `ADMIN_TOKEN` is empty. Before, an empty token made a request with no header a match.
- **Tests.**
  - `tests/unit/test_api_docs.py` (new): docs paths are 404 unless switched on, also with the
    web build mounted; they are served when switched on; the setting reads `API_DOCS`; only
    the local compose file sets it.
  - `tests/unit/test_gate.py`: `/tickets` with a wrong token is 401; the admin role without the
    token is 401 on `/approve` and `/tickets`; an empty configured token matches no request.
  - `web/src/tests/howIBuiltThis.test.tsx`: the page never links to the admin page.
- **Docs.**
  - `docs/ARCHITECTURE.md` §12 (prod compose) and §11 (web tests), `docs/security.md` and README
    step 4 describe the switch.
  - Private build context is removed from eight tracked files, wording only: `docs/SESSIONS.md`,
    `docs/ARCHITECTURE.md`, `data/SOURCES.md`, `outputs/HANDOFF_0.md`, `feedback/__init__.py`,
    `db/activity.py`, migration `0005_dashboards.py` (one comment) and
    `tests/integration/test_dashboard_views.py` (docstring). ARCHITECTURE §10 is now titled
    "The two adoption numbers".
  - README lines 31-32 are unchanged: "`#/admin`, which is not linked from the app" is true again.

## Verified

The admin endpoints on the live site (`main`, before this branch), with no token and with a
wrong one:

```
GET  /tickets  (no token)                       -> 401
POST /approve  (no token)                       -> 401
POST /approve  (no token) + X-Demo-Role: admin  -> 401
GET  /tickets  X-Admin-Token: not-the-token     -> 401
POST /approve  X-Admin-Token: not-the-token     -> 401
POST /approve  X-Admin-Token: not-the-token + X-Demo-Role: admin -> 401
```

The docs endpoints on the live site before this branch:

```
/docs                    -> 200
/redoc                   -> 404
/openapi.json            -> 200
/docs/oauth2-redirect    -> 200
```

Every route in `src/` was listed (`git grep` for route decorators). Two take the admin token,
`POST /approve` and `GET /tickets`, and both depend on `require_admin`.

Lint and unit tests:

```
$ make lint
uv run ruff check src/ tests/ eval/ .claude/hooks/
All checks passed!
uv run ruff format --check src/ tests/ eval/ .claude/hooks/
128 files already formatted
uv run mypy src/ tests/ eval/ .claude/hooks/
Success: no issues found in 123 source files

$ make test
283 passed, 63 deselected, 8 warnings in 34.54s

$ uv run pytest -m unit tests/unit/test_api_docs.py tests/unit/test_gate.py -k "docs or token or stand_in" -v
======================= 15 passed, 8 deselected in 3.10s =======================
```

The new tests fail on `main`'s code. With `main`'s `agent/api.py` restored for one run:

```
$ uv run pytest -m unit tests/unit/test_gate.py -q -k "empty_configured"
>       assert client.get("/tickets").status_code == 401
E       AssertionError: assert 200 == 401
```

With `main`'s `AQuestionArrives.tsx` restored for one run:

```
$ npx vitest run src/tests/howIBuiltThis.test.tsx -t "never links to the admin page"
   × the page never links to the admin page 450ms
AssertionError: expected [ '#/admin' ] to deeply equal []
```

How `API_DOCS` parses:

```
API_DOCS='true' -> True
API_DOCS='false' -> False
API_DOCS='1'    -> True
API_DOCS='0'    -> False
API_DOCS unset  -> False
```

Web tests and build:

```
$ cd web && npm test
 Test Files  8 passed (8)
      Tests  35 passed (35)

$ npm run build
✓ 76 modules transformed.
dist/index.html                   0.56 kB │ gzip:  0.34 kB
dist/assets/index-B8oUHZek.css   21.36 kB │ gzip:  5.09 kB
dist/assets/index-eWU1h2Qy.js   288.31 kB │ gzip: 89.37 kB
✓ built in 1.49s

$ grep -c -o '#/admin' web/dist/assets/*.js
0
```

The branch image with `API_DOCS` unset, as on the droplet, and set, as in `docker-compose.yml`.
Each line is a `TestClient` over `bas_assistant.main.app`, run with
`docker run --rm [-e API_DOCS=true] --entrypoint python bas-assistant-app:local`:

```
API_DOCS=unset {'/docs': 404, '/docs/oauth2-redirect': 404, '/openapi.json': 404, '/redoc': 404, '/healthz': 200}
API_DOCS=true  {'/docs': 200, '/docs/oauth2-redirect': 200, '/openapi.json': 200, '/redoc': 404, '/healthz': 200}
```

Stack healthy:

```
$ docker compose up -d --wait
 Container bas-assistant-postgres-1 Healthy
 Container bas-assistant-prometheus-1 Healthy
 Container bas-assistant-redis-1 Healthy
 Container bas-assistant-migrate-1 Exited
 Container bas-assistant-litellm-1 Healthy
 Container bas-assistant-grafana-1 Healthy
 Container bas-assistant-app-1 Healthy

$ docker ps -a --format 'table {{.Names}}\t{{.Status}}'
bas-assistant-app-1          Up 16 seconds (healthy)
bas-assistant-migrate-1      Exited (0) 40 seconds ago
bas-assistant-grafana-1      Up 40 seconds (healthy)
bas-assistant-litellm-1      Up 43 seconds (healthy)
bas-assistant-redis-1        Up 6 minutes (healthy)
bas-assistant-postgres-1     Up 6 minutes (healthy)
bas-assistant-prometheus-1   Up 6 minutes (healthy)
```

`make up` itself failed twice, because the laptop's Docker disk was full (59 GB, 2.6 GB free):

```
FATAL:  could not write lock file "postmaster.pid": No space left on device
dependency failed to start: container bas-assistant-postgres-1 is unhealthy
```

The first run built the image, then Postgres could not start and compose gave up; Postgres
came up by itself seconds later. The second run could not unpack the image again. The start
above therefore used the image from the first build, without `--build`. The rest of `make up`
(`make litellm-keys`, `make grafana-db-user`) was not run, and the stack was stopped afterwards
with `make down`.

The local stack, where `docker-compose.yml` sets `API_DOCS`:

```
$ docker compose exec app printenv API_DOCS
true

GET  /healthz                      -> 200
GET  /docs                         -> 200
GET  /docs/oauth2-redirect         -> 200
GET  /openapi.json                 -> 200
GET  /redoc                        -> 404
GET  /tickets (no token)           -> 401
GET  /tickets (wrong token)        -> 401
GET  /tickets (admin role only)    -> 401
POST /approve (no token)           -> 401
POST /approve (wrong token)        -> 401

bundle: assets/index-eWU1h2Qy.js
occurrences of "#/admin" in the served bundle: 0
occurrences of the new code link: 1
```

Skipped: `make test-int`. The integration file and the migration change only in a docstring
and a comment, the unit tier already imports both, and the Docker disk had no room to spare.
Also skipped: any browser click-through, and any check of this branch on the live site, which
does not change until it is deployed.

## Deferred

- `make eval` and `make redteam`: not run. They call live models, and nothing here changes
  retrieval, prompts or the graph.
- Nothing is deployed. The live site keeps serving `/docs` and the `#/admin` link until
  `deploy/deploy.sh` runs on the merged ref.

## Known gaps

- Roles still come from a header anyone can set, as `docs/security.md` says. The admin token
  protects the two admin endpoints and nothing else.
- An empty `API_DOCS=` is a startup error (Pydantic cannot read it as a boolean). Leave the
  variable unset to turn the docs off.

## Merge notes

- No dependency changes. The migration file changes in one comment only, so there is nothing to
  run. One new variable, `API_DOCS`, set only in `docker-compose.yml`; `/etc/bas-assistant.env`
  needs no edit.
- `npm run gen:api` is unaffected: it calls `app.openapi()`, which does not need the route.
- After a deploy, `/docs`, `/docs/oauth2-redirect` and `/openapi.json` on the live site should
  answer 404, and `/tickets` without a token 401.
