---
name: ci-spend
description: GitHub Actions spend rules and what to do instead of rerunning a failed job.
---

# CI spend rules

## What CI runs

One workflow (`ci.yml`), one job, triggered on `pull_request` only.
Concurrency: cancel-in-progress (same PR number cancels the prior run).

Steps: gitleaks → ruff check → ruff format → mypy → pytest -m unit.
No LLM calls. No image build or push. No deploy.

## When CI fails

**Fix locally, push once. Never rerun.**

```bash
# 1. Read the failure (gh CLI or GitHub web)
gh run view <run-id> --log-failed

# 2. Fix the issue locally
make lint   # ruff + mypy
make test   # pytest

# 3. Push — CI runs again automatically on the new commit
git push origin <branch>
```

Reruns waste Actions minutes and can introduce flaky-looking history.
The concurrency rule automatically cancels the old run when you push.

## Budget check

Free-tier orgs get 2,000 minutes/month on ubuntu-latest.
Each CI run costs roughly 2–3 minutes. At 30 PRs/month that is ~75 minutes — well within budget.

If minutes are running low:
1. Check `gh api /repos/jkhaings/bas-assistant/actions/billing/usage`
2. Never add a second workflow
3. Never add evals or model calls to CI
