# Coding Standards

Enforced by ruff, mypy, and the reviewer agent. Read this before writing code.

## Stdlib and framework first
Before writing any helper, name what in the stdlib, FastAPI, Pydantic, SQLAlchemy,
httpx, or an already-installed dependency does it. Use that. No re-implemented parsers,
retries, caches, path handling, or date math.

## Simple over clever
Flat over nested. Early returns. No metaprogramming, `__getattr__` tricks, no
decorators beyond framework ones, no comprehensions that need a comment to decode.

## Size limits (enforced: ruff/pylint)
- Functions: max 40 lines, max 5 params (more → Pydantic model or dataclass),
  max cyclomatic complexity 8, max nesting depth 3.
- Files: max 300 lines, split by domain (`ingest/`, `retrieval/`, `agent/`),
  never by type (`utils.py`, `helpers.py`, `common.py`).

## No speculative abstraction
No base class or Protocol with one implementation, no plugin systems, no config
flags for things that don't vary. Allowed interfaces: `VectorStore` and embedding
provider (see ARCHITECTURE.md). Three similar lines beat one premature helper.

## Names and comments
Names carry meaning. Comments explain *why*, never *what*. No docstrings that
restate the signature. No banner comments. No commented-out code.
`TODO` only with a matching line in the session handoff.

## Errors
Fail loudly and early. No bare `except`, no `except Exception: pass`, no try/except
around code that cannot fail, no defensive `None` checks for things the types
guarantee. Custom exceptions only if something catches them.

## Types
Type hints everywhere. mypy strict. Pydantic models at boundaries (API, DB rows,
LLM structured output, config); plain dataclasses or tuples inside. No `Any`
without a one-line reason.

## Tests test behaviour, not implementation
Never mock the thing under test. One idea per test; name says the behaviour
(`test_support_role_cannot_see_engineer_chunks`). Small fixtures. No test that
only asserts a mock was called.

## Dependencies
Adding one requires a line in `docs/adr/` with the reason and what in the stdlib
it beats. Prefer what is in the lockfile.

## Diff hygiene
Touch only what the task needs. No drive-by reformatting, renaming, or "while I'm
here" refactors. Delete dead code, never comment it out.

## Logging and output
Structured JSON logging only (`src/bas_assistant/logging.py`). No `print` (T20
bans it). No emojis in code, logs, or docs.

## Slop list — reviewer rejects on sight
- Wrapper classes around one function
- Managers/handlers/services with one method
- Config objects passed through five layers
- "Robust" retry loops around local code
- Helper modules with three unrelated functions
- `isinstance` chains where a Pydantic model would do
- String-building SQL where SQLAlchemy does it
- Giant docstrings
- Functions named `process`/`handle`/`do`/`manage`

## Ruff config summary
`line-length = 100`, select `E F W I N UP B C4 SIM C90 RUF ARG PL PIE PERF T20`,
mccabe max-complexity 8. Per-file ignores only: `tests/**` → `PLR2004`.
