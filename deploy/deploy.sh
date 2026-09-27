#!/usr/bin/env bash
# Ship a committed git ref to the droplet and release it there (deploy/release.sh).
# Usage (from the repo root on the laptop): deploy/deploy.sh root@134.122.43.193 [git-ref]
# Roll back by deploying the previous ref (cat /opt/bas-assistant/REVISION on the droplet).
#
# The droplet cannot read the private repo, so the laptop sends the tree (git archive) and the
# crawl cache in data/raw (gitignored), so an ingest there never re-crawls the vendor's site.
# On an empty corpus the release stops before Caddy: the link opens only after `make ingest`.
set -euo pipefail

TARGET=${1:?usage: deploy/deploy.sh user@host [git-ref]}
REF=${2:-HEAD}
SHA=$(git rev-parse --short "$REF")
APP_DIR=/opt/bas-assistant

git archive --format=tar "$REF" | ssh "$TARGET" "tar -x -C $APP_DIR"
rsync -a data/raw/ "$TARGET:$APP_DIR/data/raw/"
ssh "$TARGET" "$APP_DIR/deploy/release.sh $SHA"
