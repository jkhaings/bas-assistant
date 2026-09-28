# HANDOFF — docs/golden-table

Goal: in How I built this, Evaluations gets two new parts, each with a heading:
- "The golden set", with a table of every golden case.
- "LLM as a judge".

The red-team sentence and the closing staff-rating sentence stay.

## Built

- `web/src/pages/howIBuiltThis/Evaluations.tsx` (moved out of `AroundItAll.tsx`):
  - "The golden set": the pasted paragraph, then the table.
  - "LLM as a judge": the pasted text, with the four metrics as a list.
  - Then the kept red-team and staff-rating sentences, and the Tools line.
  - The old RAGAS sentence is replaced by the judge part, so `RUN.faithfulness` was unused and
    is removed.
- Changes to the pasted text, each checked against the repo:
  - "It's 22 questions" became "It's 20 questions", because `eval/golden.jsonl` has 20 lines and
    the table shows 20 rows. "I ask all 22 again" became "I ask them all again". The table
    caption explains the 22: each run makes 22 checks, because 2 questions are asked as two
    roles. The caption computes both numbers from the file.
  - "The judge doesn't get the internet or my notes. It only sees three things: …" became "The
    judge doesn't get the internet. It only sees four things: …, and the right answer from my
    key."
    - `eval/ragas_run.py` `_score()` sends `reference`, and `evals/golden.py` sets that to the
      case's `expected_fact`.
    - Context recall and context precision score against it.
  - "$0.03 for the answers" became "$0.02". `eval/results/latest.md` line 3 says "Cost $0.0529
    (answers $0.0220, RAGAS judge $0.0309)". The judge's $0.03 was right.
  - "gpt-4o-mini" is unchanged. `ragas_run.py` uses the `fast` alias, and
    `config/litellm.yaml` maps `fast` to `openai/gpt-4o-mini`.
  - 0.111 is unchanged, and it now comes from `RUN.protocolFaithfulness`. The costs are
    `RUN.evalAnswersUsd` and `RUN.evalJudgeUsd` in `run.ts`.
- `web/src/pages/howIBuiltThis/GoldenTable.tsx`:
  - It reads `eval/golden.jsonl` at build time with a `?raw` import, so there is no API call and
    no copy of the file to drift.
  - Columns: #, Category, Question, Expected, Source document (with the page), Role.
  - The two engineer-only rows show "abstain as support, answer as engineer" and "support,
    engineer".
  - On a phone (below the `sm` width), each row stacks into a card and each cell shows its column
    name. From `sm` up, it is a normal table.
- Build plumbing for reading a file outside `web/`:
  - `Dockerfile` web stage: `COPY eval/golden.jsonl /eval/golden.jsonl`.
  - `.dockerignore`: `!eval/golden.jsonl` after `eval/`.
  - `web/vite.config.ts`: `server.fs.allow: [".", "../eval"]`. Vite checks a `?raw` id against
    the allow list with the query attached, so allowing only the file was denied ("Denied ID …").
- `web/src/tests/howIBuiltThis.test.tsx`: one new test reads `eval/golden.jsonl?raw` and checks
  that the table has exactly that many body rows, and more than zero.
- `docs/ARCHITECTURE.md` §11: the table, the build plumbing and the new test.

## Verified

### Facts in the judge text

```
$ sed -n 3p eval/results/latest.md
Corpus version `2.112.2026-09-27T23:17:56.018010+00:00`, prompt version `a2d7b390625a`. Cost $0.0529 (answers $0.0220, RAGAS judge $0.0309).
$ grep -n 'model_name="fast"' eval/ragas_run.py
67:        model_name="fast",
$ grep -n "model_name: fast$" -A2 config/litellm.yaml
6:  - model_name: fast
7-    litellm_params:
8-      model: openai/gpt-4o-mini
$ grep -n "reference" eval/ragas_run.py src/bas_assistant/evals/golden.py
eval/ragas_run.py:109:                "reference": result.reference,
src/bas_assistant/evals/golden.py:48:    reference: str
src/bas_assistant/evals/golden.py:118:        reference=case.expected_fact,
src/bas_assistant/evals/golden.py:136:        reference=case.expected_fact,
```

### Web tests

```
$ cd web && npm test
 Test Files  8 passed (8)
      Tests  33 passed (33)
$ npx vitest run --reporter=verbose src/tests/howIBuiltThis.test.tsx
 ✓ src/tests/howIBuiltThis.test.tsx > How I built this has the three steps, then Known problems 146ms
 ✓ src/tests/howIBuiltThis.test.tsx > the nine sections follow the pipeline, each ending with its tools 39ms
 ✓ src/tests/howIBuiltThis.test.tsx > the page is written in the first person, never as we 19ms
 ✓ src/tests/howIBuiltThis.test.tsx > the golden table has one row per case in eval/golden.jsonl 21ms
```

### Web build, local and in the image

```
$ cd web && npm run build
dist/assets/index-B8oUHZek.css   21.36 kB │ gzip:  5.09 kB
dist/assets/index-BPFCtI-P.js   288.32 kB │ gzip: 89.39 kB
✓ built in 160ms

$ docker build --progress=plain --no-cache-filter web -t bas-assistant-app:golden-check .
#16 [web 6/7] COPY eval/golden.jsonl /eval/golden.jsonl
#17 [web 7/7] RUN npm run build
#17 3.417 ✓ 76 modules transformed.
#17 4.286 ✓ built in 1.22s
#33 naming to docker.io/library/bas-assistant-app:golden-check done
```

The test tag was removed afterwards.

### Phone and desktop layout

- The build was served with `vite preview` and screenshotted in headless Chrome.
- Phone: the page was loaded in a 390 px iframe, because headless Chrome's window has a minimum
  width of about 500 px. A plain 390 px window only crops a wider layout, and that is what
  made the first attempt look cut off.
- Checked at 390 px:
  - Each case is a labelled card.
  - Long questions and `UNOnext-MODBUS-RTU-Protocol, page 3` wrap inside the 16 px gutters.
  - Nothing runs off the screen.
- The first build did overflow: the `<table>` and `<tbody>` kept table layout while the rows
  were blocks. Making them `block` below `sm`, and wrapping each cell's value in a `min-w-0`
  span, fixed it.
- Checked at 1280 px: a six-column table.

### Repo checks

```
$ make lint
Success: no issues found in 122 source files
$ make test
273 passed, 63 deselected, 8 warnings in 18.89s
```

### Skipped

- Deploy: not asked for.

## Deferred

- Nothing from the task.

## Known gaps

- The golden rows are cast from JSON without a runtime check. The file is in the repo and read
  at build time, and a malformed line fails the build. No TODO.

## Merge notes

- `Dockerfile` and `.dockerignore` change. The next deploy's image build copies
  `eval/golden.jsonl` into the web stage; `deploy.sh` syncs it because it is tracked.
- No migrations, env vars or dependency changes.
