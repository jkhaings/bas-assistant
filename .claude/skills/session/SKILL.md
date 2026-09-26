---
name: session
description: Start and complete a build session (A–E). Creates the worktree, builds, runs acceptance checks, writes the handoff, updates ARCHITECTURE.md, fixes reviewer issues, commits and pushes.
argument-hint: <A|B|C|D|E>
---

# /session $ARGUMENTS

Run session **$ARGUMENTS** from start to committed push.

## Session branch map

| Letter | Branch | Worktree |
|---|---|---|
| A | `a-retrieval` | `../bas-assistant-wt/a-retrieval` |
| B | `b-graph` | `../bas-assistant-wt/b-graph` |
| C | `c-guardrails` | `../bas-assistant-wt/c-guardrails` |
| D | `d-observability` | `../bas-assistant-wt/d-observability` |
| E | `e-ship` | `../bas-assistant-wt/e-ship` |

## Steps (execute in order, stop only on unresolvable blockers)

1. **Read** (do not skip):
   - `CLAUDE.md` — operating rules
   - `docs/CODING_STANDARDS.md` — mandatory standards
   - `docs/ARCHITECTURE.md` — design of record
   - `docs/SESSIONS.md` — the block for session $ARGUMENTS
   - `outputs/HANDOFF_*.md` if any — prior session state

2. **Create worktree and branch** (skip if already exists):
   ```
   git worktree add ../bas-assistant-wt/<branch> -b <branch> main
   ```
   Copy `CLAUDE.local.md` into the worktree root if it exists here.

3. **Install dependencies** in the worktree:
   ```
   cd ../bas-assistant-wt/<branch> && uv sync --dev
   ```

4. **Build** everything the session block specifies. Follow `docs/CODING_STANDARDS.md`.
   Every new module goes in the domain directory, not a utils file.

5. **Run acceptance checks** exactly as listed in the session block. Capture real output.
   Do not claim a check passes without showing the command and its output.

6. **Write `outputs/HANDOFF_$ARGUMENTS.md`** — use the `/handoff` format.
   Claims without pasted output are bugs.

7. **Update `docs/ARCHITECTURE.md`** — mark built things as built, deferred things as deferred.
   Follow the Build Status table at the top.

8. **Run the reviewer agent** (`/reviewer` subagent) on `git diff main`.
   Fix every blocking issue. Re-run `make lint` and `make test` after fixes.

9. **Commit** in the worktree:
   ```
   git add -A
   git commit -m "feat: session $ARGUMENTS — <one-line summary>"
   ```

10. **Push once**:
    ```
    git push origin <branch>
    ```
    Stop. Do not merge. Do not push again.
