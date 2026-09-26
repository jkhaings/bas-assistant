---
name: preflight
description: Run the five-step preflight check and print a pass/fail report.
---

# /preflight

Run these five steps in order. Print one line per step: PASS or FAIL + why.

```bash
make lint          # ruff + mypy
make test          # pytest -m unit
docker compose config --quiet   # compose file is valid
docker compose up -d --build --wait   # all services healthy
curl -sf http://localhost:8000/healthz   # app responds
```

Final line: `PREFLIGHT: PASS` or `PREFLIGHT: FAIL — <step that failed>`.

If any step fails, stop and fix before continuing.
