.DEFAULT_GOAL := help
.PHONY: help up down test test-int lint format check-env preflight ingest eval redteam

PYTHON  := uv run python
PYTEST  := uv run pytest
RUFF    := uv run ruff
MYPY    := uv run mypy

# ── required env variable names (values never printed) ──────────────────────
REQUIRED_VARS := OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY ADMIN_TOKEN \
                 LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY GRAFANA_ADMIN_PASSWORD

help:
	@echo "Targets: up down test test-int lint format check-env preflight ingest eval redteam"

# ── secret guard ─────────────────────────────────────────────────────────────
check-env:
	@ENV_FILE="$$HOME/.bas-assistant.env"; \
	if [ ! -f "$$ENV_FILE" ]; then \
	  echo "ERROR: $$ENV_FILE not found. Create it from .env.example." >&2; exit 1; \
	fi; \
	MODE=$$(stat -f "%Mp%Lp" "$$ENV_FILE" 2>/dev/null || stat -c "%a" "$$ENV_FILE" 2>/dev/null); \
	if [ "$$MODE" != "0600" ] && [ "$$MODE" != "600" ]; then \
	  echo "ERROR: $$ENV_FILE must be mode 600 (got $$MODE). Run: chmod 600 $$ENV_FILE" >&2; exit 1; \
	fi; \
	. "$$ENV_FILE"; \
	MISSING=""; \
	for VAR in $(REQUIRED_VARS); do \
	  VAL=$$(eval echo \$$$$VAR); \
	  if [ -z "$$VAL" ]; then MISSING="$$MISSING $$VAR"; fi; \
	done; \
	if [ -n "$$MISSING" ]; then \
	  echo "ERROR: Empty variables (fill them with nano, not echo):$$MISSING" >&2; exit 1; \
	fi; \
	echo "check-env: OK"

# ── docker ───────────────────────────────────────────────────────────────────
up: check-env
	docker compose up -d --build --wait

down:
	docker compose down

# ── tests ────────────────────────────────────────────────────────────────────
test:
	$(PYTEST) -m unit

test-int:
	@echo "not implemented until session A" >&2; exit 1

# ── quality ──────────────────────────────────────────────────────────────────
lint:
	$(RUFF) check src/ tests/ .claude/hooks/
	$(RUFF) format --check src/ tests/ .claude/hooks/
	$(MYPY) src/ tests/ .claude/hooks/

format:
	$(RUFF) format src/ tests/ .claude/hooks/
	$(RUFF) check --fix src/ tests/ .claude/hooks/

# ── preflight ────────────────────────────────────────────────────────────────
preflight: lint test
	docker compose config --quiet
	docker compose up -d --build --wait
	curl -sf http://localhost:8000/healthz
	@echo "preflight: PASS"

# ── data ─────────────────────────────────────────────────────────────────────
ingest:
	@echo "not implemented until session A" >&2; exit 1

eval:
	@echo "not implemented until session C" >&2; exit 1

redteam:
	@echo "not implemented until session C" >&2; exit 1
