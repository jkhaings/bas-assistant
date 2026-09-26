# bas-assistant

> Work in progress — building toward a live demo at https://bas.jasonkhaings.com.

An internal support assistant for a building-automation company. Staff ask product questions;
the assistant answers from ingested public documentation (Delta Controls catalog sheets and product
pages) with page citations, abstains when the documents don't cover it, and can propose an internal
ticket that a human approves. Everything is permission-filtered, cost-metered, traced, and evaluated.

Built as a portfolio project. Not affiliated with Delta Controls.

## How to run locally

```bash
# 1. Fill in your API keys (never echo — use nano)
cp .env.example ~/.bas-assistant.env
chmod 600 ~/.bas-assistant.env
nano ~/.bas-assistant.env

# 2. Verify the env file is ready
make check-env

# 3. Start the app
make up          # docker compose up -d --build --wait

# 4. Smoke test
curl http://localhost:8000/healthz   # → {"status":"ok"}

# 5. Run unit tests and linter
make test
make lint
```

## Docs

- [Architecture](docs/ARCHITECTURE.md) — design of record, keep current-state truthful
- [Coding Standards](docs/CODING_STANDARDS.md) — mandatory, read before writing code
- [Security keys](docs/security-keys.md) — key locations, rotation procedure
- [Session plan](docs/SESSIONS.md) — weekend build schedule, sessions A–E
