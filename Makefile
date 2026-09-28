.DEFAULT_GOAL := help
.PHONY: help up down test test-int lint format check-env preflight ingest eval redteam \
        litellm-keys litellm-secrets observability-secrets grafana-db-user

PYTHON  := uv run python
PYTEST  := uv run pytest
RUFF    := uv run ruff
MYPY    := uv run mypy
ALEMBIC := uv run alembic

# ── required env variable names (values never printed) ──────────────────────
# Proxy admin key and the two virtual keys; `make litellm-secrets` generates them
LITELLM_VARS := LITELLM_MASTER_KEY LITELLM_API_KEY LITELLM_SERVICE_KEY
# Langfuse project keys and the Grafana reader's password; `make observability-secrets`
OBSERVABILITY_VARS := LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY GRAFANA_DB_PASSWORD
REQUIRED_VARS := OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY ADMIN_TOKEN \
                 GRAFANA_ADMIN_PASSWORD POSTGRES_PASSWORD $(LITELLM_VARS) $(OBSERVABILITY_VARS)
# Langfuse's containers read only this file: its variable names (POSTGRES_PASSWORD,
# DATABASE_URL) collide with ours, and they have no use for the vendor keys.
LANGFUSE_ENV := $$HOME/.bas-assistant-langfuse.env
# Grafana is publicly reachable, so it gets its two passwords and nothing else.
GRAFANA_ENV := $$HOME/.bas-assistant-grafana.env

# Host-side runs: load the env file, then reach the compose services on their published ports
WITH_ENV  := set -a && . "$$HOME/.bas-assistant.env" && set +a &&
HOST_URLS := POSTGRES_HOST=localhost POSTGRES_PORT=5433 LITELLM_BASE_URL=http://localhost:4000 \
             EMBED_BASE_URL=http://localhost:4000/v1 REDIS_URL=redis://localhost:6379/0

help:
	@echo "Targets: up down test test-int lint format check-env preflight ingest eval redteam"
	@echo "         litellm-keys litellm-secrets observability-secrets grafana-db-user"

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
	for SIDE_FILE in "$(LANGFUSE_ENV)" "$(GRAFANA_ENV)"; do \
	  if [ ! -f "$$SIDE_FILE" ]; then \
	    echo "ERROR: $$SIDE_FILE not found. Run: make observability-secrets" >&2; exit 1; \
	  fi; \
	  SIDE_MODE=$$(stat -f "%Mp%Lp" "$$SIDE_FILE" 2>/dev/null || stat -c "%a" "$$SIDE_FILE" 2>/dev/null); \
	  if [ "$$SIDE_MODE" != "0600" ] && [ "$$SIDE_MODE" != "600" ]; then \
	    echo "ERROR: $$SIDE_FILE must be mode 600 (got $$SIDE_MODE)." >&2; exit 1; \
	  fi; \
	done; \
	echo "check-env: OK"

# ── docker ───────────────────────────────────────────────────────────────────
up: check-env
	docker compose up -d --build --wait
	$(MAKE) litellm-keys
	$(MAKE) grafana-db-user

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

# Append the Langfuse project keys and the Grafana reader's password to the main env file if
# missing, then write Grafana's and Langfuse's own env files once; values are never printed
observability-secrets:
	@ENV_FILE="$$HOME/.bas-assistant.env"; LF_FILE="$(LANGFUSE_ENV)"; GF_FILE="$(GRAFANA_ENV)"; \
	add() { grep -q "^$$1=." "$$ENV_FILE" || { printf '%s=%s\n' "$$1" "$$2" >> "$$ENV_FILE"; echo "added $$1"; }; }; \
	add LANGFUSE_PUBLIC_KEY "pk-lf-$$(openssl rand -hex 16)"; \
	add LANGFUSE_SECRET_KEY "sk-lf-$$(openssl rand -hex 16)"; \
	add GRAFANA_DB_PASSWORD "$$(openssl rand -hex 24)"; \
	set -a; . "$$ENV_FILE"; set +a; \
	umask 077; \
	if [ -f "$$GF_FILE" ]; then echo "$$GF_FILE exists, left as is"; else \
	  { echo "GRAFANA_ADMIN_PASSWORD=$$GRAFANA_ADMIN_PASSWORD"; \
	    echo "GRAFANA_DB_PASSWORD=$$GRAFANA_DB_PASSWORD"; } > "$$GF_FILE"; \
	  echo "wrote $$GF_FILE"; \
	fi; \
	if [ -f "$$LF_FILE" ]; then echo "$$LF_FILE exists, left as is"; exit 0; fi; \
	PG=$$(openssl rand -hex 24); MINIO=$$(openssl rand -hex 24); \
	{ \
	  echo "LANGFUSE_INIT_PROJECT_PUBLIC_KEY=$$LANGFUSE_PUBLIC_KEY"; \
	  echo "LANGFUSE_INIT_PROJECT_SECRET_KEY=$$LANGFUSE_SECRET_KEY"; \
	  echo "LANGFUSE_INIT_USER_PASSWORD=$$(openssl rand -hex 12)"; \
	  echo "NEXTAUTH_SECRET=$$(openssl rand -hex 32)"; \
	  echo "SALT=$$(openssl rand -hex 32)"; \
	  echo "ENCRYPTION_KEY=$$(openssl rand -hex 32)"; \
	  echo "CLICKHOUSE_PASSWORD=$$(openssl rand -hex 24)"; \
	  echo "REDIS_AUTH=$$(openssl rand -hex 24)"; \
	  echo "POSTGRES_PASSWORD=$$PG"; \
	  echo "DATABASE_URL=postgresql://postgres:$$PG@langfuse-postgres:5432/postgres"; \
	  echo "MINIO_ROOT_PASSWORD=$$MINIO"; \
	  echo "LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY=$$MINIO"; \
	  echo "LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY=$$MINIO"; \
	} > "$$LF_FILE"; \
	echo "wrote $$LF_FILE"

# Login for the read-only role behind Grafana's Postgres data source (migration 0005); the
# password reaches psql through the environment, never the command line.
# On the droplet, deploy/release.sh sets it before Grafana starts.
# TODO(post-weekend): locally Grafana starts first, so the first alert evaluations after a fresh
# `make up` fail on the login (HANDOFF_E.md).
grafana-db-user:
	@$(WITH_ENV) printf '%s\n' '\getenv pw GRAFANA_DB_PASSWORD' \
	  "ALTER ROLE grafana_reader LOGIN PASSWORD :'pw';" \
	  | docker compose exec -T -e GRAFANA_DB_PASSWORD postgres \
	    psql -q -v ON_ERROR_STOP=1 -U bas_assistant -d bas_assistant
	@echo "grafana-db-user: OK"

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
# TODO(post-weekend): on the 4 GB droplet a cold ingest beside the running app fills RAM and
# swap; stop the app and run it in a one-off container (README runbook, HANDOFF_E.md).
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
