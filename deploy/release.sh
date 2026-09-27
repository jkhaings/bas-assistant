#!/usr/bin/env bash
# The droplet half of deploy/deploy.sh: build, migrate, restart, smoke. Runs in /opt/bas-assistant
# as root after the tree for the ref has been unpacked there. Usage: deploy/release.sh <short-sha>
# Every docker command gets no stdin, so none of them can read from the ssh session.
set -euo pipefail

SHA=${1:?usage: deploy/release.sh <short-sha>}
cd "$(dirname "$0")/.."
set -a; . /etc/bas-assistant.env; set +a
for key in OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY; do
  if [ -z "${!key}" ]; then
    echo "release: $key is empty; paste it with: nano /etc/bas-assistant.env" >&2
    exit 1
  fi
done

docker compose build app </dev/null
docker tag bas-assistant-app:prod "bas-assistant-app:$SHA"
docker compose up -d --wait postgres redis </dev/null
docker compose run --rm -T migrate </dev/null
# Grafana's data source logs in as grafana_reader, so the password is set before Grafana starts
# (it reaches psql through the environment, never the command line).
printf '%s\n' '\getenv pw GRAFANA_DB_PASSWORD' "ALTER ROLE grafana_reader LOGIN PASSWORD :'pw';" \
  | docker compose exec -T -e GRAFANA_DB_PASSWORD postgres \
    psql -q -v ON_ERROR_STOP=1 -U bas_assistant -d bas_assistant
docker compose up -d --wait app litellm prometheus grafana </dev/null
docker compose exec -T -e LITELLM_BASE_URL=http://litellm:4000 app \
  python -m bas_assistant.llm.provision </dev/null
echo "$SHA" > REVISION

documents=$(docker compose exec -T postgres \
  psql -tA -U bas_assistant -d bas_assistant -c 'select count(*) from documents' </dev/null)
if [ "$documents" = 0 ]; then
  echo "release: $SHA is up without Caddy, because the corpus is empty."
  echo "release: run 'make ingest' in $PWD, then deploy again to open the link."
  exit 0
fi

docker compose up -d --wait caddy </dev/null
# The first start obtains the certificate, so the smoke calls retry until TLS is ready.
curl -sf --retry 20 --retry-delay 3 --retry-all-errors "https://$DOMAIN/healthz"
echo
curl -sf --retry 3 --retry-all-errors "https://$DOMAIN/ask" -H 'Content-Type: application/json' -H 'X-Demo-Role: support' \
  -d '{"question":"How many inputs and outputs does the eZNT-T331 network thermostat have?"}' \
  | python3 -c 'import json, sys; r = json.load(sys.stdin); print("smoke /ask:", r["decision"], len(r["citations"]), "citations, cache_hit", r["cache_hit"])'
echo "release: $SHA is live at https://$DOMAIN"
