# bas-assistant

An internal support assistant for a building-automation company. Staff ask product questions;
it answers only from ingested public Delta Controls documentation with page citations, abstains
when the docs don't cover it, and can propose an internal ticket that a human approves.
Public portfolio repo: github.com/jkhaings/bas-assistant. Live demo: https://bas.jasonkhaings.com.

## Design of record

**`docs/ARCHITECTURE.md` is always current-state truth.** When you build or defer something,
update it. Do not leave it describing a future that hasn't shipped.

## Mandatory standards

**Read `docs/CODING_STANDARDS.md` before writing any code.** The reviewer agent enforces it.

## Operating rules

- Python 3.12, FastAPI, Pydantic v2, pytest, ruff, mypy. Type hints everywhere.
- Secrets only from environment. Never write a key into any file.
  `gitleaks` pre-commit hook and Claude hooks are active.
- Every model call goes through LiteLLM aliases (`fast` / `strong` / `embed`),
  never a vendor SDK directly except inside `config/litellm.yaml`.
- Every session ends with: `make test` green, `docker compose up` healthy,
  and `outputs/HANDOFF_<X>.md` with real pasted output. No claims without output.
- GitHub Actions: one workflow, one job, `pull_request` only, no LLM calls.
  Never add a second workflow. Never rerun (fix locally, push once).
- Do not merge. Commit on the branch, push once, stop.
- Corpus: public documents only. Source URLs in `data/SOURCES.md`.
  Never touch `support.deltacontrols.com` (SSO-gated; denied in `.claude/settings.json`).
- Time-box: if a library fights you for 30 minutes, take the documented fallback.

## Logging rule

Never log request headers, raw env vars, settings objects, or raw questions.
Only the Presidio-redacted question appears in logs.

## Repo layout

```
src/bas_assistant/   # application code (split by domain: ingest/, retrieval/, agent/)
tests/unit/          # no network, no docker, fake LLM and retriever
tests/integration/   # real Postgres via docker compose
tests/eval/          # golden-set eval, requires live system
tests/redteam/       # red-team suite, local only
.claude/hooks/       # Claude Code PreToolUse / PostToolUse hooks
.claude/skills/      # slash commands
.claude/agents/      # subagent definitions
docs/adr/            # architecture decision records
config/              # litellm.yaml, grafana provisioning
deploy/              # Caddyfile, setup_server.sh, deploy.sh
```

## Branches and worktrees

| Branch | Worktree |
|---|---|
| `a-retrieval` | `../bas-assistant-wt/a-retrieval` |
| `b-graph` | `../bas-assistant-wt/b-graph` |
| `c-guardrails` | `../bas-assistant-wt/c-guardrails` |
| `d-observability` | `../bas-assistant-wt/d-observability` |
| `e-ship` | `../bas-assistant-wt/e-ship` |

## Make targets

`up` `down` `test` `test-int` `lint` `format` `check-env` `preflight` `ingest` `eval` `redteam`

## Test tiers (pytest markers)

- `unit`: no network, no docker, deterministic, fake LLM, hash embedder
- `integration`: real Postgres in compose
- `eval`: live LLM and corpus (`make eval`, local only)
- `redteam`: live system, local only (`make redteam`)

## Commits

Conventional commits: `feat: ...`, `fix: ...`, `chore: ...`, `test: ...`, `docs: ...`.

## How to reply to Jason

Short. Direct. No flattery. Numbered steps. Run commands instead of describing them.
