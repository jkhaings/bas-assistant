#!/usr/bin/env bash
# Ship a committed git ref to the droplet, build it there, migrate and restart.
# Usage (from the repo root on the laptop): deploy/deploy.sh root@134.122.43.193 [git-ref]
# Roll back by deploying the previous ref (cat /opt/bas-assistant/REVISION on the droplet).
#
# The droplet cannot read the private repo, so the laptop sends the tree (git archive) and the
# crawl cache in data/raw (gitignored), so an ingest there never re-crawls the vendor's site.
# On an empty corpus it stops before Caddy: the public link opens only after `make ingest`.
set -euo pipefail

TARGET=${1:?usage: deploy/deploy.sh user@host [git-ref]}
REF=${2:-HEAD}
SHA=$(git rev-parse --short "$REF")
APP_DIR=/opt/bas-assistant

git archive --format=tar "$REF" | ssh "$TARGET" "tar -x -C $APP_DIR"
rsync -a data/raw/ "$TARGET:$APP_DIR/data/raw/"

ssh "$TARGET" bash -s -- "$SHA" "$APP_DIR" <<'REMOTE'
set -euo pipefail
SHA=$1
cd "$2"
set -a; . /etc/bas-assistant.env; set +a
for key in OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY; do
  if [ -z "${!key}" ]; then
    echo "deploy: $key is empty; paste it with: nano /etc/bas-assistant.env" >&2
    exit 1
  fi
done

docker compose build app
docker tag bas-assistant-app:prod "bas-assistant-app:$SHA"
docker compose up -d --wait postgres redis
docker compose run --rm migrate
# Grafana's data source logs in as grafana_reader, so the password is set before Grafana starts
# (the password reaches psql through the environment, never the command line).
printf '%s\n' '\getenv pw GRAFANA_DB_PASSWORD' "ALTER ROLE grafana_reader LOGIN PASSWORD :'pw';" \
  | docker compose exec -T -e GRAFANA_DB_PASSWORD postgres \
    psql -q -v ON_ERROR_STOP=1 -U bas_assistant -d bas_assistant
docker compose up -d --wait app litellm prometheus grafana
docker compose exec -T -e LITELLM_BASE_URL=http://litellm:4000 app \
  python -m bas_assistant.llm.provision
echo "$SHA" > REVISION

documents=$(docker compose exec -T postgres \
  psql -tA -U bas_assistant -d bas_assistant -c 'select count(*) from documents')
if [ "$documents" = 0 ]; then
  echo "deploy: $SHA is up without Caddy, because the corpus is empty."
  echo "deploy: run 'make ingest' in $PWD, then deploy again to open the link."
  exit 0
fi

docker compose up -d --wait caddy
curl -sf "https://$DOMAIN/healthz"
echo
curl -sf "https://$DOMAIN/ask" -H 'Content-Type: application/json' -H 'X-Demo-Role: support' \
  -d '{"question":"How many inputs and outputs does the eZNT-T331 network thermostat have?"}' \
  | python3 -c 'import json, sys; r = json.load(sys.stdin); print("smoke /ask:", r["decision"], len(r["citations"]), "citations, cache_hit", r["cache_hit"])'
echo "deploy: $SHA is live at https://$DOMAIN"
REMOTE
