.DEFAULT_GOAL := help
.PHONY: help up down test test-int lint format check-env preflight ingest eval redteam \
        litellm-keys litellm-secrets

PYTHON  := uv run python
PYTEST  := uv run pytest
RUFF    := uv run ruff
MYPY    := uv run mypy

# ── required env variable names (values never printed) ──────────────────────
# Proxy admin key and the two virtual keys; `make litellm-secrets` generates them
LITELLM_VARS := LITELLM_MASTER_KEY LITELLM_API_KEY LITELLM_SERVICE_KEY
REQUIRED_VARS := OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY ADMIN_TOKEN \
                 GRAFANA_ADMIN_PASSWORD $(LITELLM_VARS)
# Optional until session D mints them from the self-hosted Langfuse instance
OPTIONAL_LANGFUSE_VARS := LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY

# Host-side URLs for the compose services (inside compose the service names are used)
HOST_URLS := DATABASE_URL=postgresql://bas@localhost:5433/bas \
             REDIS_URL=redis://localhost:6379/0 LITELLM_BASE_URL=http://localhost:4000
WITH_ENV  := set -a && . "$$HOME/.bas-assistant.env" && set +a &&

help:
	@echo "Targets: up down test test-int lint format check-env preflight ingest eval redteam"
	@echo "         litellm-keys litellm-secrets"

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
	for VAR in $(OPTIONAL_LANGFUSE_VARS); do \
	  VAL=$$(eval echo \$$$$VAR); \
	  if [ -z "$$VAL" ]; then echo "WARN: $$VAR empty (expected until session D)"; fi; \
	done; \
	echo "check-env: OK"

# ── docker ───────────────────────────────────────────────────────────────────
up: check-env
	docker compose up -d --build --wait
	$(MAKE) litellm-keys

# Register the dev ($5/month) and service ($2/month) virtual keys with the proxy
litellm-keys:
	@$(WITH_ENV) $(HOST_URLS) $(PYTHON) -m bas_assistant.llm.provision

# Append a random value for each missing LITELLM_* variable; values are never printed
litellm-secrets:
	@ENV_FILE="$$HOME/.bas-assistant.env"; \
	for VAR in $(LITELLM_VARS); do \
	  if grep -q "^$$VAR=." "$$ENV_FILE"; then continue; fi; \
	  printf '%s=sk-%s\n' "$$VAR" "$$(openssl rand -hex 24)" >> "$$ENV_FILE"; \
	  echo "added $$VAR"; \
	done

down:
	docker compose down

# ── tests ────────────────────────────────────────────────────────────────────
test:
	$(PYTEST) -m unit

# Separate database and Redis db, so fake-proxy rows never reach the app's spend totals
TEST_URLS := DATABASE_URL=postgresql://bas@localhost:5433/bas_test \
             REDIS_URL=redis://localhost:6379/1

test-int:
	$(TEST_URLS) uv run alembic upgrade head
	$(TEST_URLS) uv run alembic check
	$(TEST_URLS) $(PYTEST) -m integration

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

# Live models through the local proxy. Session C adds the golden set and RAGAS.
eval:
	@$(WITH_ENV) $(HOST_URLS) $(PYTEST) -m eval

redteam:
	@echo "not implemented until session C" >&2; exit 1
