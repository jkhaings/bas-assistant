# HANDOFF — hotfix/web-build

`deploy/deploy.sh root@134.122.43.193 main` failed in the Dockerfile's `web` stage:
`RUN npm run build` exited with code 2.

Root cause: `deploy.sh` untarred `git archive <ref>` straight over `/opt/bas-assistant`. Files a
ref deletes were never removed from the droplet. main deleted nine web files after the last good
deploy (`1949e6c`), and ui/simple had renamed `ApprovalsPage.tsx` before that. `tsc -b`
type-checks everything under `web/src`, so it compiled the stale files. They import things main
has since removed: `FeedbackValue`, `Steps`, and old `RUN` fields.

The Dockerfile, `.dockerignore` and the web code were all correct. A build from a clean checkout
passes. The fix belongs in the deploy, not in the types.

## Built

- `deploy/deploy.sh`: the ref is unpacked into an empty staging directory,
  `/opt/bas-assistant-incoming`. It is then synced over `/opt/bas-assistant` with
  `rsync -a --delete`, and the staging directory is removed.
  - `KEEP` lists the droplet's own state, which no ref contains: `/.env` (the link to
    `/etc/bas-assistant.env`), `/REVISION`, `/data/raw/`, `/.venv/` and
    `/eval/results/*.jsonl`.
  - Everything else untracked is deleted, which includes the stale web files and the
    `__pycache__` directories.
  - The `*.jsonl` glob is single-quoted so the droplet's shell passes it to rsync unexpanded.
- `deploy/deploy.sh` header: the "files a newer ref added stay" note and its
  `TODO(post-weekend)` are removed, and the comment explains the sync and `KEEP`.
- `README.md` "Roll back" and `docs/ARCHITECTURE.md` (deploy paragraph): describe the sync.

## Verified

### The droplet's tree (read only)

```
$ ssh root@134.122.43.193 'cat /opt/bas-assistant/REVISION; ls /opt/bas-assistant/web/src/pages/howIBuiltThis'
1949e6c
AQuestionArrives.tsx AroundItAll.tsx BeforeAQuestion.tsx Cost.tsx Evals.tsx InsideACompany.tsx
KnownProblems.tsx LangGraph.tsx Problem.tsx RequestPath.tsx Section.tsx TwentyQuestions.tsx
Weaknesses.tsx run.ts
$ git diff --name-status --diff-filter=D 246a9f9 HEAD
D	web/src/components/chat/FeedbackControl.tsx
D	web/src/pages/howIBuiltThis/Cost.tsx
D	web/src/pages/howIBuiltThis/Evals.tsx
D	web/src/pages/howIBuiltThis/InsideACompany.tsx
D	web/src/pages/howIBuiltThis/LangGraph.tsx
D	web/src/pages/howIBuiltThis/Problem.tsx
D	web/src/pages/howIBuiltThis/RequestPath.tsx
D	web/src/pages/howIBuiltThis/TwentyQuestions.tsx
D	web/src/pages/howIBuiltThis/Weaknesses.tsx
```

The only untracked files on the droplet were `.env`, `REVISION`, `data/raw/`, `.venv/`,
`.pytest_cache/`, `eval/results/golden-latest.jsonl`, the `__pycache__` directories, and the ten
stale web files. I got this list by comparing `find` on the droplet with
`git ls-tree -r HEAD`.

### The failure, reproduced locally

The build context is built the way the droplet's tree was: `git archive 1949e6c` unpacked, then
`git archive 44b43c2` (main) unpacked over it.

```
$ docker build --progress=plain --target web <overlaid tree>
#12 [web 6/6] RUN npm run build
#12 3.858 src/components/chat/FeedbackControl.tsx(4,15): error TS2305: Module '"../../api/types"' has no exported member 'FeedbackValue'.
#12 3.859 src/pages/howIBuiltThis/Cost.tsx(19,22): error TS2339: Property 'abstainUsd' does not exist on type '{ documents: number; ... }'.
#12 3.859 src/pages/howIBuiltThis/Cost.tsx(20,70): error TS2339: Property 'evalRunUsd' does not exist on type '{ ... }'.
#12 3.859 src/pages/howIBuiltThis/Evals.tsx(31,61): error TS2339: Property 'golden' does not exist on type '{ ... }'.
#12 3.859 src/pages/howIBuiltThis/Evals.tsx(58,42): error TS2339: Property 'redteam' does not exist on type '{ ... }'.
#12 3.859 src/pages/howIBuiltThis/RequestPath.tsx(2,19): error TS2305: Module '"./Section"' has no exported member 'Steps'.
#12 3.859 src/pages/howIBuiltThis/TwentyQuestions.tsx(26,66): error TS2339: Property 'chunks' does not exist on type '{ ... }'.
#12 3.859 src/pages/howIBuiltThis/Weaknesses.tsx(14,45): error TS2339: Property 'p95Seconds' does not exist on type '{ ... }'.
#12 ERROR: process "/bin/sh -c npm run build" did not complete successfully: exit code: 2
```

The long `RUN` type literals are shortened to `{ ... }` above. A clean checkout of main builds
the same stage without errors (`✓ built in 1.20s`).

### The fix, on the same tree, with the droplet's rsync version

The `KEEP` line was taken from `deploy/deploy.sh` and run as the droplet's shell would run it, in
`python:3.12-slim-bookworm` with rsync 3.2.7 (the droplet also has 3.2.7). Fake droplet state was
added first: the `.env` link, `REVISION`, `data/raw/`, `.venv/`, the eval jsonl and a
`__pycache__`.

```
rsync  version 3.2.7  protocol version 32
--- stale web files left (want none):
--- droplet state kept (want all 5):
/w/app/.env -> /etc/bas-assistant.env
1949e6c
/w/app/.venv/bin:
python
/w/app/data/raw:
cached.pdf
/w/app/eval/results:
golden-latest.jsonl
latest.md
--- caches deleted (want gone):
ls: cannot access '/w/app/src/bas_assistant/__pycache__': No such file or directory
--- app vs staged tree, outside KEEP (want no output):
```

```
$ docker build --progress=plain --no-cache --target web <synced tree>
#12 [web 6/6] RUN npm run build
#12 3.585 ✓ 73 modules transformed.
#12 3.668 ✓ built in 260ms
#13 naming to docker.io/library/bas-web-repro:latest done
```

### Full image, from the repo

```
$ docker build --progress=plain --no-cache-filter web -t bas-assistant-app:hotfix-web-build .
#16 [web 6/6] RUN npm run build
#16 3.103 ✓ 73 modules transformed.
#16 3.252 ✓ built in 416ms
#32 naming to docker.io/library/bas-assistant-app:hotfix-web-build done
full build exit 0
```

`--no-cache-filter web` rebuilds the web stage uncached; the Python stages came from cache
(`uv.lock` is unchanged). The test tags were removed afterwards.

### Local web build and tests

```
$ cd web && npm run build
dist/index.html                   0.56 kB │ gzip:  0.34 kB
dist/assets/index-D9QJRz7m.css   20.20 kB │ gzip:  4.86 kB
dist/assets/index-C66Rx_2J.js   279.00 kB │ gzip: 86.75 kB
✓ built in 161ms
$ npm test
 Test Files  8 passed (8)
      Tests  32 passed (32)
```

### Script and repo checks

```
$ bash -n deploy/deploy.sh && echo "syntax ok"
syntax ok
$ shellcheck -S warning deploy/deploy.sh && echo "shellcheck: no warnings"
shellcheck: no warnings
$ make lint
Success: no issues found in 122 source files
$ make test
273 passed, 63 deselected, 8 warnings in 19.00s
```

### Skipped

- Running the new `deploy.sh` against the droplet: the task said to commit, push once and stop.
  The next deploy is the first real run.

## Deferred

- Nothing from the task.

## Known gaps

- `KEEP` is a list of paths to keep, so any other untracked file under `/opt/bas-assistant` is
  deleted on deploy. That is the intent, but new droplet-side state has to be added to `KEEP`.
  The comment in `deploy.sh` says so. No TODO: this is the design.
- `.pytest_cache/` is not kept, because it is a cache.

## Merge notes

- No migrations, env vars, dependency or Dockerfile changes.
- The first deploy after this merge deletes the stale web files and every `__pycache__` on the
  droplet, then builds as the clean checkout does.
