---
name: handoff
description: Format specification for outputs/HANDOFF_<X>.md. Use when writing a session handoff document.
---

# Handoff format

Every `outputs/HANDOFF_<X>.md` must have these five sections in order.
**Claims without pasted output are bugs — a reviewer will reject them.**

---

## Built

List every item from the session block that was completed, one line each.
Be specific: "chunker with parent-child, overlap 50, table-row guard" not "ingestion done".

## Verified

For each acceptance check in the session block, paste:
1. The exact command run
2. The verbatim output (trimmed to the relevant lines if very long, but never paraphrased)

Example:
```
$ make test
...........
15 passed in 0.42s
```

If a check was skipped, say why explicitly.

## Deferred

Items from the session block that were NOT completed, with a one-line reason each.
"Not started" is a valid reason only if the session block itself said so.

## Known gaps

Things that work but have known limitations or technical debt. These are not bugs —
they are documented shortfalls. Each gap gets a matching TODO in the relevant source file.

## Merge notes

What the next session or Jason's merge step needs to know:
- Which tables or columns Alembic adds
- Which env vars are new
- Any pyproject.toml dependency additions
- Conflicts that are predictable (e.g. "both A and B add to docker-compose.yml")
- Any `alembic heads` > 1 issue
