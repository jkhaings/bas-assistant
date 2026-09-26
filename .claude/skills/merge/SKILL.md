---
name: merge
description: Jason's by-hand merge order for sessions A–E. Paste-ready command blocks with expected output.
---

# Merge order: A → B → C → D → E

Jason does all merges by hand. One branch at a time. One push per branch. Never force-push.

## Pre-merge checklist

Before touching main:
- `git status` is clean on main
- `make test` is green on main
- `alembic heads` returns exactly one head

## Session A

```bash
cd bas-assistant
git fetch origin
git merge --no-ff origin/a-retrieval -m "feat: merge session A — retrieval and ingestion"
make test
```

Expected: `make test` green. Then:

```bash
git push origin main
```

Expected: `To https://github.com/jkhaings/bas-assistant.git`

## Session B (rebase on A first)

```bash
cd ../bas-assistant-wt/b-graph
git rebase origin/a-retrieval
# resolve any conflicts, then:
git push --force-with-lease origin b-graph
cd ../../bas-assistant
git merge --no-ff origin/b-graph -m "feat: merge session B — gateway, graph, human gate"
make test
git push origin main
```

## Session C

```bash
git merge --no-ff origin/c-guardrails -m "feat: merge session C — guardrails and evaluation"
make test
git push origin main
```

## Session D

```bash
git merge --no-ff origin/d-observability -m "feat: merge session D — observability"
make test
git push origin main
```

## Session E

```bash
git merge --no-ff origin/e-ship -m "feat: merge session E — UI, deploy, how-I-built-this"
make test
git push origin main
```

## Conflict checklist

| File | How to resolve |
|---|---|
| `uv.lock` | Delete it, run `uv lock`, stage the new one — never hand-merge |
| `pyproject.toml` deps | Union of both sides |
| `docker-compose.yml` | Add both sets of services; keep healthchecks |
| `Makefile` targets | Add both sets; keep "not implemented" stubs |
| `docs/ARCHITECTURE.md` | Keep the more-complete version; merge deferred lists |
| `alembic/versions/` | Check `alembic heads`; if > 1, create a merge migration |

## Post-merge gate

After every merge push:
```bash
make lint && make test
```

Both must be clean before continuing to the next session merge.
