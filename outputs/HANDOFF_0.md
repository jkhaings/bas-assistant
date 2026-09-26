# Session 0 handoff

## Built

- `~/.bas-assistant.env` template (mode 600) with 7 secret keys and `DAILY_USD_CAP=3`
- `.env.example` with key names only (tracked)
- `docs/CODING_STANDARDS.md` — 70 lines, full rule set
- `docs/security-keys.md` — key locations, spend limits, rotation procedure, leak procedure
- `docs/adr/0001-stack.md` — one-line-per-decision table (21 decisions)
- `docs/adr/0002-dependencies.md` — running dependency log
- `data/SOURCES.md` — public corpus roots, FORBIDDEN flag on SSO-gated domain
- `docs/ARCHITECTURE.md` — Build Status table added, CI section updated to current state
- `pyproject.toml` — ruff (E F W I N UP B C4 SIM C90 RUF ARG PL PIE PERF T20), mypy strict + pydantic plugin, pytest markers
- `src/bas_assistant/settings.py` — `Settings(BaseSettings)`, SecretStr fields, env only
- `src/bas_assistant/logging.py` — JSON formatter, `RedactingFilter`, `configure_logging()`
- `src/bas_assistant/main.py` — FastAPI app, `GET /healthz`
- `src/bas_assistant/__main__.py` — uvicorn entry point with `log_config=None`
- `tests/unit/` — 31 unit tests across 4 files; fixture `fake_keys.txt`
- `.gitignore`, `.dockerignore`, `.editorconfig`
- `Dockerfile` (multi-stage, non-root, no ENV/ARG for keys)
- `docker-compose.yml` (app only, env_file from `$HOME`)
- `Makefile` — all targets including `check-env`, `preflight`; unbuilt targets exit 1
- `.github/pull_request_template.md`, `.github/workflows/ci.yml`
- `README.md` — two paragraphs, links, no feature claims
- Folder stubs with `.gitkeep`: `deploy/`, `outputs/`, `web/`, `eval/`, `config/`
- `.gitleaks.toml` — allowlists `.env.example` and `fake_keys.txt`
- `.pre-commit-config.yaml` — pygrep key shapes, gitleaks, ruff format, ruff check
- `.claude/hooks/guard_bash.py` — PreToolUse Bash guard (14 deny patterns)
- `.claude/hooks/block_key_shapes.py` — PreToolUse Write/Edit key shape blocker
- `.claude/hooks/gitleaks_on_commit.py` — PreToolUse Bash (if: git commit) gitleaks scanner
- `.claude/hooks/ruff_on_edit.py` — PostToolUse Write/Edit ruff formatter
- `.claude/settings.json` — deny rules + hooks
- `.claude/settings.local.json` — additionalDirectories for worktree root (gitignored)
- `CLAUDE.md` — 81 lines, operating contract, repo layout, branch/worktree map
- `CLAUDE.local.md` — private context: deadline, drop order, job application context
- `.claude/skills/` — 7 skills: session, handoff, merge, preflight, ci-spend, arch-sync, simplify
- `.claude/agents/` — 3 agents: reviewer, test-runner, arch-auditor
- `uv.lock` committed (Python 3.12, all deps resolved)
- pre-commit hooks installed at `.git/hooks/pre-commit`

## Verified

**uv sync**
```
$ uv sync --dev
# all packages resolved from lock file
$ ls .venv/bin/ | grep -E "pytest|ruff|mypy|pre-commit"
mypy  pre-commit  pytest  ruff
```

**make lint — CLEAN**
```
$ uv run ruff check src/ tests/ .claude/hooks/
All checks passed!
$ uv run ruff format --check src/ tests/ .claude/hooks/
15 files already formatted
$ uv run mypy src/ tests/ .claude/hooks/
Success: no issues found in 15 source files
```

**make test — GREEN**
```
$ uv run pytest -m unit -v
collected 31 items
tests/unit/test_claude_hooks.py .........................   [ 80%]
tests/unit/test_healthz.py .                               [ 83%]
tests/unit/test_logging.py .                               [ 87%]
tests/unit/test_no_secrets.py ....                         [100%]
======================== 31 passed, 1 warning in 1.17s =========================
```
(Warning: starlette TestClient deprecation re httpx2 — not blocking, affects session E only)

**pre-commit run --all-files**
```
$ uv run pre-commit run --all-files
No API key shapes in staged files........................................Passed
gitleaks — scan staged diff for secrets..................................Passed
ruff format..........................................(no files to check)Skipped
ruff check --fix.....................................(no files to check)Skipped
```

**gitleaks — working tree and full history**
```
$ gitleaks git --redact --no-banner
1 commits scanned. no leaks found. EXIT: 0

$ gitleaks dir . --redact --no-banner
scanned ~258309 bytes (258.31 KB) in 86.1ms. no leaks found. EXIT: 0
```

**Fake-key commit blocked by pre-commit hooks**
```
$ python3 -c "import secrets; key='ghp_'+secrets.token_hex(18); open('scratch.txt','w').write(key)"
$ git add scratch.txt
$ uv run pre-commit run --files scratch.txt
No API key shapes in staged files........................................Failed
  hook id: no-key-shapes; exit code: 1
  scratch.txt:1:ghp_1b3588a8e2b5f6d0bbc57...
gitleaks — scan staged diff for secrets..................................Failed
  hook id: gitleaks; exit code: 1
  leaks found: 1
$ git restore --staged scratch.txt && rm scratch.txt
$ git status --short  # scratch.txt gone
```

**Claude block_key_shapes hook — verified via test suite**
```
test_write_guard_blocks_key_shapes    PASSED
test_write_guard_allows_the_fixture_path  PASSED
```

**Claude guard_bash hook — verified via test suite**
```
test_bash_guard_blocks_dangerous_commands[11 parametrize cases]  ALL PASSED
test_bash_guard_allows_everyday_commands[12 parametrize cases]   ALL PASSED
```

**make check-env — fails naming empty variables, no values printed**
```
$ make check-env
ERROR: Empty variables (fill them with nano, not echo): OPENAI_API_KEY ANTHROPIC_API_KEY
  GEMINI_API_KEY ADMIN_TOKEN LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY GRAFANA_ADMIN_PASSWORD
make: *** [check-env] Error 1
```

**docker compose config --quiet — valid**
```
$ docker compose config --quiet
EXIT: 0
```

## Deferred

- `make up` / `docker compose up` — keys are empty, so app can't start yet (expected). Session A adds the DB services and real corpus. This is correct behaviour.
- `make test-int`, `make ingest`, `make eval`, `make redteam` — exit 1 with "not implemented until session X" (intentional stubs).
- CI (`.github/workflows/ci.yml`) — works on PR, not tested here (no PR yet).
- Reviewer agent run on own diff — deferred to after commit (nothing to diff yet before the first commit).

## Known gaps

- starlette/httpx TestClient deprecation warning (tests/unit/test_healthz.py) — harmless, fixed in session E when the web layer moves to httpx2.
- `gitleaks_on_commit.py` fires on every `git commit` Bash command, including commits in worktrees. This is intentional — each worktree has its own copy of the hooks.

## Merge notes

- This is the initial commit on `main`. Sessions A–E branch from here.
- New `[dependency-groups]` section in `pyproject.toml` for dev deps (uv format).
- Worktrees go into `../bas-assistant-wt/<branch>`. Create parent dir if it doesn't exist.
