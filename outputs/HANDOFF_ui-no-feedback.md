# HANDOFF — ui/no-feedback

Goal: remove the "Did you use this answer?" widget (Used as-is / Used with edits / Not used)
from the chat. The feedback endpoint, its tests, the usage rows and the Quality & adoption
dashboard panel are unchanged. Added mid-task: remove the "Why LangGraph, and what the human
gate does" section from How I built this. Only `web/` and the docs changed.

## Built

- `web/src/components/chat/FeedbackControl.tsx`: deleted.
- `web/src/components/chat/AnswerView.tsx`: no feedback control. An answer's footer now has
  "Flag as wrong" and "Show cost".
- `web/src/api/types.ts`: `FeedbackValue` removed. It had no other users.
  `POST /requests/{request_id}/feedback` stays in the generated `schema.d.ts`.
- `web/src/tests/chat.test.tsx`: the two widget tests are removed. They covered a vote being
  recorded and a rejected vote. A new test checks that an answer has no used-as-is,
  used-with-edits or not-used buttons.
- How I built this, `Problem.tsx` (the section on the two numbers):
  - The old line said every answer carries buttons for both numbers. It now says every answer
    carries "Flag as wrong" for the second, and the Dashboards tab shows both.
  - The added sentence: "In a real deployment the support team rates each answer used as-is,
    used with edits or not used, and that is where the adoption number comes from; this public
    demo hides those buttons because its visitors are not the support team."
- `web/src/pages/howIBuiltThis/LangGraph.tsx`: deleted, and removed from `HowIBuiltThis.tsx`.
  That section was the only place on the page that explained the gate and `#/admin`. The
  README's Human gate bullet still does. The gate itself is unchanged.
- `web/src/pages/howIBuiltThis/RequestPath.tsx`: the screenshot TODO now also lists the
  feedback buttons.
- `docs/ARCHITECTURE.md`:
  - §10 "Used without edits": the support team rates answers in a deployment; the demo hides
    the buttons; the endpoint and the panel stay.
  - §11: the feedback buttons are removed from the product line, the chat bullets and the tests
    list.

## Verified

### Nothing under the backend, eval, test or config trees changed

```
$ git diff HEAD -- src/ tests/ eval/ config/ | wc -l
       0
```

### make lint

```
$ make lint
uv run ruff check src/ tests/ eval/ .claude/hooks/
All checks passed!
uv run ruff format --check src/ tests/ eval/ .claude/hooks/
127 files already formatted
uv run mypy src/ tests/ eval/ .claude/hooks/
Success: no issues found in 122 source files
```

### make test

```
$ make test
273 passed, 63 deselected, 8 warnings in 18.67s
```

The feedback endpoint's own tests, unchanged:

```
$ uv run pytest -m unit -v tests/unit/test_feedback.py
============================== 8 passed in 0.97s ===============================
```

### Web tests

```
$ cd web && npm test
 Test Files  7 passed (7)
      Tests  29 passed (29)
```

The count went from 30 to 29: two widget tests were removed and one no-buttons test was added.

### Web build

```
$ cd web && npm run build
dist/index.html                   0.56 kB │ gzip:  0.34 kB
dist/assets/index-lEcAur-d.css   21.20 kB │ gzip:  5.04 kB
dist/assets/index-DPDYzX2E.js   280.13 kB │ gzip: 86.94 kB
✓ built in 149ms
```

### Skipped

- `docker compose up` and deploy: not in the task's checks, and nothing to deploy was asked for.

## Deferred

- Nothing from the task.

## Known gaps

- The live demo no longer records adoption votes. The Quality & adoption panel's used-as-is
  number will keep only the votes cast before this change. No TODO: this is by design.
- The screenshots `docs/img/live-chat.png` and `web/public/img/chat-answer.png` still show the
  feedback buttons, and their alt texts describe them. Recapture them, then update both alt
  texts. The TODO is in `web/src/pages/howIBuiltThis/RequestPath.tsx`, already open from
  HANDOFF_ui-simple.md.

## Merge notes

- No migrations, env vars or dependency changes.
- Branched from main at `1949e6c` (after the ui/simple merge).
