# HANDOFF — docs/how-i-built

Goal: rewrite How I built this as a first-person story that follows the pipeline in the order
things happen. It has three steps, nine sections, a "Tools:" line closing each section, and four
known problems. Only `web/` and ARCHITECTURE.md changed.

## Built

- Structure, titles verbatim:
  - Step 1: Before anyone asks a question, with RAG: the documents and Embeddings.
  - Step 2: A question arrives, with Guardrails, Routing, Search and Orchestration.
  - Step 3: Around all of it, with Cost tracking, Security and Evaluations.
  - Known problems, four items.
- Every section has 5 sentences, in first person, with no "we". A script counted the sentences
  and found no sentence longer than 25 words. Each section ends with a "Tools:" line and one
  link:
  - Repo paths: `ingest/`, `retrieval/embeddings.py`, `guardrails/`, `llm/router.py`,
    `retrieval/` and `api/roles.py`.
  - App pages: `#/admin` (Orchestration), Dashboards (Cost tracking) and Evals (Evaluations).
- Tools are named from the code and pyproject, not guessed:
  - httpx, selectolax, Docling with pypdfium2, LlamaIndex.
  - text-embedding-3-small, pgvector, Presidio with `en_core_web_sm`, Redis.
  - LiteLLM with the models in `config/litellm.yaml`.
  - SQLAlchemy, sentence-transformers with `cross-encoder/ms-marco-MiniLM-L-6-v2`.
  - LangGraph with its Postgres checkpointer, FastAPI.
  - Prometheus, Grafana, pydantic-settings, gitleaks (`.pre-commit-config.yaml`), Caddy.
  - pytest, RAGAS with the `fast` alias (gpt-4o-mini) as the judge.
- Every number was checked against the code:
  - 10 s crawl delay, 300-token chunks, 1,536 dimensions.
  - 20 questions a minute per IP, top 20 reranked, five sections, one retry.
  - `$3` cap resetting at midnight UTC, 6 red-team cases.
- Known problems, each checked against its source:
  - Protocol faithfulness 0.111: `eval/results/latest.md`.
  - Sibling sections crowding the top five: the old Evals section.
  - No ticket from a fault report that isn't in the docs: `HANDOFF_E.md`. The graph abstains at
    retrieval, before the answer model.
  - 8 catalog PDFs returning 403: `HANDOFF_C.md`, `HANDOFF_E.md`.
- Screenshots kept: `chat-answer.png` in Orchestration and `grafana-budget.png` in Cost
  tracking. The recapture TODO moved with `chat-answer.png` into `AQuestionArrives.tsx`.
- Evaluations keeps the ui/no-feedback point, stated as built behaviour: staff can rate answers,
  and the demo hides the buttons.
- Removed:
  - `Problem`, `TwentyQuestions`, `RequestPath`, `Cost`, `Evals` and `Weaknesses`. Their content
    is replaced by the sections above.
  - `InsideACompany`: it was about planned work, which the spec rules out.
  - Unused `RUN` fields.
- Files:
  - `web/src/pages/howIBuiltThis/Section.tsx`: `Part` (h2), `Section` (h3) and `Tools`.
  - One file per step: `BeforeAQuestion.tsx`, `AQuestionArrives.tsx`, `AroundItAll.tsx`.
  - `KnownProblems.tsx`.
- `web/src/tests/howIBuiltThis.test.tsx`: the step and section headings verbatim and in order,
  four known problems, each section's last line starting "Tools: ", and no "we", "our" or "us".
- `docs/ARCHITECTURE.md` §11: describes the page's new shape and the new test.

## Verified

### Nothing under the backend, eval, test or config trees changed

```
$ git diff HEAD -- src/ tests/ eval/ config/ | wc -l
       0
```

### Web tests

```
$ cd web && npm test
 Test Files  8 passed (8)
      Tests  32 passed (32)

$ npx vitest run --reporter=verbose src/tests/howIBuiltThis.test.tsx
 ✓ src/tests/howIBuiltThis.test.tsx > How I built this has the three steps, then Known problems 127ms
 ✓ src/tests/howIBuiltThis.test.tsx > the nine sections follow the pipeline, each ending with its tools 21ms
 ✓ src/tests/howIBuiltThis.test.tsx > the page is written in the first person, never as we 7ms
```

### Web build

```
$ cd web && npm run build
dist/index.html                   0.56 kB │ gzip:  0.34 kB
dist/assets/index-D9QJRz7m.css   20.20 kB │ gzip:  4.86 kB
dist/assets/index-C66Rx_2J.js   279.00 kB │ gzip: 86.75 kB
✓ built in 154ms
```

### make lint and make test (no Python changed; run anyway)

```
$ make lint
Success: no issues found in 122 source files
$ make test
273 passed, 63 deselected, 8 warnings in 18.54s
```

### Skipped

- `docker compose up` and deploy: not in the task's checks.

## Deferred

- Nothing from the task.

## Known gaps

- `chat-answer.png` and the README's `docs/img/live-chat.png` still show the old top bar and
  feedback buttons. The TODO is in `web/src/pages/howIBuiltThis/AQuestionArrives.tsx`.
- The page no longer has the p95 latency or the per-role allowance points from the old "What it
  does badly" list. The spec fixed Known problems at four items. The README still lists both.
  No TODO: this is by design.

## Merge notes

- Stacked on `ui/no-feedback` (`5207563`), which is not merged yet. Merge `ui/no-feedback`
  first. Branching from main would have hit a modify/delete conflict on `Problem.tsx`, and the
  page would describe a chat without feedback buttons while main still has them.
- No migrations, env vars or dependency changes.
