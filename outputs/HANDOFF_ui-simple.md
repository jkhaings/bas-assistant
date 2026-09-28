# HANDOFF — ui/simple

Goal: make the public UI simpler without removing any backend feature. Every visitor asks as
support, the ticket flow stays off the chat, and the role switcher, admin token and approve
controls moved to `#/admin`, a route reached only by its URL. Only `web/`, the docs and one
Caddyfile comment changed. The API, graph, ACL filter, migrations, evals and red team did not.

## Built

- `web/src/hooks/useHashRoute.ts`: the `approvals` route is now `admin`. An old `#/approvals` link
  falls back to Chat.
- `web/src/components/NavTabs.tsx`: the Approvals tab is removed. No tab or link points to
  `#/admin`.
- `web/src/components/TopBar.tsx`: the "View as" select is removed. The top bar has the name,
  budget chip, documents chip and tabs.
- `web/src/pages/AdminPage.tsx` (renamed with `git mv` from `ApprovalsPage.tsx`): the "View as"
  select above the unchanged token form and ticket board. The header says the role applies to
  every page, including Chat, and that each role keeps its own threads.
- `web/src/App.tsx`: role state stays in App (default `support`), so a role picked on `#/admin`
  applies to Chat. That keeps the gate demo working: pick Engineer, ask in Chat, pick Admin,
  approve.
- `web/src/components/chat/AnswerView.tsx`: the ticket callout and the notes list are removed.
  A turn with `approval_required` or with a note shows "Flagged for follow-up" in one line of
  small grey text. A paused turn's badge reads answered when it cites a passage and abstained
  when it does not, which matches how the graph's `finish` closes it.
- `web/src/components/chat/NodeSteps.tsx`: the chat's path hides `propose_ticket`, `human_gate`
  and `act`.
- `web/src/components/chat/ThreadList.tsx`: "one list per role" is removed from the chat
  sidebar.
- How I built this: `LangGraph.tsx` gets a new paragraph. The roles and the gate are unchanged,
  they are demonstrated on `#/admin`, and it gives the three steps to see the gate. The paragraph
  shows `#/admin` as code text, not a link. `Weaknesses.tsx` now says visitors ask as support by
  default.
- Tests:
  - `roleSwitch.test.tsx`: the main screen has no switcher, admin token field or Approvals
    link, and it sends `X-Demo-Role: support`. The role switch is tested on `#/admin`.
  - `approvals.test.tsx`: the approval tests now open `#/admin`.
  - `chat.test.tsx`: four tests replace the paused-callout test. They cover the flagged line
    with no ticket controls, the path without ticket steps, an abstained paused turn and the
    support no-ticket note.
- Docs:
  - `README.md` line 3: "no login; you ask as support".
  - `README.md` Human gate bullet: points to `#/admin`.
  - `README.md` allowance weakness: rewritten for the support default.
  - `docs/ARCHITECTURE.md` §1 roles, §11 routes, top bar, chat, Admin and tests: current state.
  - `docs/ARCHITECTURE.md` deployment note: says where the switcher lives now.
- `deploy/Caddyfile`: a comment-only change ("the Approvals tab" → "the admin page").

## Verified

### Nothing under the backend, eval or test trees changed

```
$ git diff HEAD -- src/ eval/ tests/ config/ | wc -l
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
273 passed, 63 deselected, 8 warnings in 18.94s
```

### Web tests

```
$ cd web && npm test
 Test Files  7 passed (7)
      Tests  30 passed (30)
```

Changed and new tests (from `npx vitest run --reporter=verbose` on the three files):

```
 ✓ src/tests/roleSwitch.test.tsx > the main screen asks as support with no role switcher, admin token or Approvals tab 189ms
 ✓ src/tests/roleSwitch.test.tsx > viewing as Engineer on #/admin sends the engineer role and updates the documents count 50ms
 ✓ src/tests/approvals.test.tsx > an admin with a token approves a proposed ticket and sees it filed 323ms
 ✓ src/tests/approvals.test.tsx > a rejected token is cleared and the admin is asked again 71ms
 ✓ src/tests/approvals.test.tsx > roles other than admin are told to switch 6ms
 ✓ src/tests/chat.test.tsx > a turn that drafts a ticket shows the answer flagged for follow-up, no ticket controls 135ms
 ✓ src/tests/chat.test.tsx > the chat's path leaves out the ticket steps 129ms
 ✓ src/tests/chat.test.tsx > a drafted ticket with no citation shows as abstained 115ms
 ✓ src/tests/chat.test.tsx > a ticket suggested to a role that cannot file one is flagged, not explained 119ms
```

### Web build

```
$ cd web && npm run build
> tsc -b && vite build
dist/index.html                   0.56 kB │ gzip:  0.34 kB
dist/assets/index-lEcAur-d.css   21.20 kB │ gzip:  5.04 kB
dist/assets/index-BtkYkYOg.js   282.44 kB │ gzip: 87.60 kB
✓ built in 150ms
```

### Skipped

- `docker compose up`: the task's checks were lint, unit tests, web tests and the web build.
  The only image change is the web stage, which `npm run build` covers.
- Deploy: the task said not to deploy.

## Deferred

- Nothing from the task.

## Known gaps

- The screenshots `docs/img/live-chat.png` (README) and `web/public/img/chat-answer.png` (How I
  built this) still show the "View as" select and the Approvals tab. Recapture them from the
  live site after the next deploy. TODO in `web/src/pages/howIBuiltThis/RequestPath.tsx`.
- `AskResponse` has no `needs_ticket` field, so the UI reads `approval_required` and `notes`. It
  relies on `NO_TICKET_NOTE` being the graph's only note; a new kind of note would be hidden and
  shown as "Flagged for follow-up". TODO in `web/src/components/chat/AnswerView.tsx`.
- An unanswerable paused turn (engineer or admin only, reached after switching roles on
  `#/admin`) shows the graph's own text: "The documentation does not cover this, so I drafted a
  ticket for an admin to review." Changing it means changing the graph, which this task ruled
  out. Support never reaches this. The TODO is the same one in `AnswerView.tsx`.
- After a role switch on `#/admin`, the main screen shows no role label; only the documents
  count changes. This is by design, and the admin page says it.

## Merge notes

- No migrations, env vars or dependency changes.
- The web route `#/approvals` is now `#/admin`. External links to `#/approvals` land on Chat.
- The `deploy/Caddyfile` change is a comment only; the next deploy reloads an identical config.
- Not deployed. The live site still shows the old UI until `deploy/deploy.sh` runs on this ref.
