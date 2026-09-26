## What

<!-- One paragraph: what changed and why. -->

## How verified

<!-- Paste the real command and its output. Claims without output are bugs. -->

```
$ make test
...
```

## Output pasted

- [ ] `make lint` clean
- [ ] `make test` green
- [ ] `docker compose up` healthy (or no compose change)
- [ ] `outputs/HANDOFF_<X>.md` written with real output

## Standards followed

- [ ] No new helpers named `process`/`handle`/`do`/`manage`
- [ ] No re-implemented stdlib functionality
- [ ] No bare `except` or `except Exception: pass`
- [ ] Types complete; no new `Any` without comment
- [ ] No secrets in code, logs, or tests (outside allowlisted fixture)

## Architecture updated

- [ ] `docs/ARCHITECTURE.md` reflects what was built or explicitly deferred
