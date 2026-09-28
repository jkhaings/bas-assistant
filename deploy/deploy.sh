#!/usr/bin/env bash
# Ship a committed git ref to the droplet and release it there (deploy/release.sh).
# Usage (from the repo root on the laptop): deploy/deploy.sh root@<host> [git-ref]
# Roll back by deploying the previous ref (cat /opt/bas-assistant/REVISION on the droplet).
# Migrations never run down; a rollback across a migration needs `alembic downgrade` first.
#
# The ref is unpacked into an empty staging directory and synced over the app directory with
# --delete, so a file the ref no longer tracks is removed. Unpacked straight over the old tree,
# deleted web files stayed and `tsc -b` in the image's web stage failed on them. KEEP is the
# droplet's own state, which no ref contains: the .env link, REVISION, the crawl cache, the
# virtualenv `make ingest` uses, and the live eval results. Anything else untracked is deleted.
#
# The droplet cannot read the private repo, so the laptop sends the tree (git archive) and the
# crawl cache in data/raw (gitignored), so an ingest there never re-crawls the vendor's site.
# On an empty corpus the release stops before Caddy: the link opens only after `make ingest`.
set -euo pipefail

TARGET=${1:?usage: deploy/deploy.sh user@host [git-ref]}
REF=${2:-HEAD}
SHA=$(git rev-parse --short "$REF")
APP_DIR=/opt/bas-assistant
STAGE_DIR=/opt/bas-assistant-incoming
KEEP="--exclude=/.env --exclude=/REVISION --exclude=/data/raw/ --exclude=/.venv/"
KEEP+=" --exclude='/eval/results/*.jsonl'"

git archive --format=tar "$REF" \
  | ssh "$TARGET" "rm -rf $STAGE_DIR && mkdir $STAGE_DIR && tar -x -C $STAGE_DIR"
ssh "$TARGET" "rsync -a --delete $KEEP $STAGE_DIR/ $APP_DIR/ && rm -rf $STAGE_DIR"
rsync -a data/raw/ "$TARGET:$APP_DIR/data/raw/"
ssh "$TARGET" "$APP_DIR/deploy/release.sh $SHA"
