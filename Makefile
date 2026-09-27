.DEFAULT_GOAL := help
.PHONY: help up down test test-int lint format check-env preflight ingest eval redteam \
        litellm-keys litellm-secrets

PYTHON  := uv run python
PYTEST  := uv run pytest
RUFF    := uv run ruff
MYPY    := uv run mypy
ALEMBIC := uv run alembic

# ── required env variable names (values never printed) ──────────────────────
# Proxy admin key and the two virtual keys; `make litellm-secrets` generates them
LITELLM_VARS := LITELLM_MASTER_KEY LITELLM_API_KEY LITELLM_SERVICE_KEY
REQUIRED_VARS := OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY ADMIN_TOKEN \
                 GRAFANA_ADMIN_PASSWORD POSTGRES_PASSWORD $(LITELLM_VARS)
# Optional until session D mints them from the self-hosted Langfuse instance
OPTIONAL_LANGFUSE_VARS := LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY

# Host-side runs: load the env file, then reach the compose services on their published ports
WITH_ENV  := set -a && . "$$HOME/.bas-assistant.env" && set +a &&
HOST_URLS := POSTGRES_HOST=localhost POSTGRES_PORT=5433 LITELLM_BASE_URL=http://localhost:4000 \
             EMBED_BASE_URL=http://localhost:4000/v1 REDIS_URL=redis://localhost:6379/0

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

# bas_test and Redis db 1, so test rows never reach the app's spend totals or cache
test-int: check-env
	@ENV_FILE="$$HOME/.bas-assistant.env"; \
	set -a; . "$$ENV_FILE"; set +a; \
	export POSTGRES_HOST=localhost POSTGRES_PORT=5433 POSTGRES_DB=bas_test \
	       REDIS_URL=redis://localhost:6379/1; \
	$(ALEMBIC) upgrade head && $(ALEMBIC) check && $(PYTEST) -m integration

# ── quality ──────────────────────────────────────────────────────────────────
lint:
	$(RUFF) check src/ tests/ eval/ .claude/hooks/
	$(RUFF) format --check src/ tests/ eval/ .claude/hooks/
	$(MYPY) src/ tests/ eval/ .claude/hooks/

format:
	$(RUFF) format src/ tests/ eval/ .claude/hooks/
	$(RUFF) check --fix src/ tests/ eval/ .claude/hooks/

# ── preflight ────────────────────────────────────────────────────────────────
preflight: lint test
	docker compose config --quiet
	docker compose up -d --build --wait
	curl -sf http://localhost:8000/healthz
	@echo "preflight: PASS"

# ── data ─────────────────────────────────────────────────────────────────────
ingest:
	docker compose exec app python -m bas_assistant.ingest

# Live models through the local proxy: the golden set (and B's live checks), then RAGAS over
# the golden answers. RAGAS runs even when a golden case fails; either failing fails the target.
eval:
	@$(WITH_ENV) $(HOST_URLS) $(PYTEST) -m eval; golden=$$?; \
	$(WITH_ENV) $(HOST_URLS) $(PYTHON) eval/ragas_run.py && cat eval/results/latest.md; ragas=$$?; \
	[ $$golden -eq 0 ] && [ $$ragas -eq 0 ]

# Attacks against the running stack; writes an eval_runs row (kind redteam).
redteam:
	@$(WITH_ENV) $(HOST_URLS) $(PYTEST) -m redteam
