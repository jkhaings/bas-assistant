#!/usr/bin/env bash
# One-time preparation of a fresh Ubuntu 24.04 droplet: Docker, firewall, unattended upgrades,
# swap, the app directory and the production env file. Safe to run again.
# Run as root from the laptop: ssh root@<host> 'bash -s' < deploy/setup_server.sh
set -euo pipefail

APP_DIR=/opt/bas-assistant
ENV_FILE=/etc/bas-assistant.env
export DEBIAN_FRONTEND=noninteractive

# Docker CE and the compose plugin from Docker's own repository: Ubuntu's docker.io package
# lags the compose features the stack uses (include, profiles, --wait).
if ! command -v docker >/dev/null; then
  apt-get update
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  codename=$(. /etc/os-release && echo "$VERSION_CODENAME")
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc]" \
    "https://download.docker.com/linux/ubuntu $codename stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin \
    docker-compose-plugin
fi
apt-get install -y make rsync ufw unattended-upgrades

# Docker-published ports bypass ufw, which is why the prod compose binds every service except
# Caddy to 127.0.0.1.
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

# 4 GB of RAM holds the stack; an ingest (Docling) on top of it needs somewhere to spill.
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
echo 'vm.swappiness=10' > /etc/sysctl.d/99-bas-assistant.conf
sysctl -q -p /etc/sysctl.d/99-bas-assistant.conf

mkdir -p "$APP_DIR/data/raw"

# The only place production secrets live. Generated values are never printed. The vendor keys
# come from the vendors' consoles, so a person pastes them: nano /etc/bas-assistant.env
if [ ! -f "$ENV_FILE" ]; then
  umask 077
  cat > "$ENV_FILE" <<EOF
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
ADMIN_TOKEN=$(openssl rand -hex 24)
POSTGRES_PASSWORD=$(openssl rand -hex 24)
LITELLM_MASTER_KEY=sk-$(openssl rand -hex 24)
LITELLM_API_KEY=sk-$(openssl rand -hex 24)
LITELLM_SERVICE_KEY=sk-$(openssl rand -hex 24)
GRAFANA_ADMIN_PASSWORD=$(openssl rand -hex 24)
GRAFANA_DB_PASSWORD=$(openssl rand -hex 24)
DAILY_USD_CAP=3
DOMAIN=bas.jasonkhaings.com
COMPOSE_FILE=docker-compose.prod.yml
EOF
fi
chmod 600 "$ENV_FILE"
# Compose reads .env in the project directory (COMPOSE_FILE, and the Grafana and Caddy values it
# interpolates); the Makefile's eval and redteam targets read ~/.bas-assistant.env.
ln -sfn "$ENV_FILE" "$APP_DIR/.env"
ln -sfn "$ENV_FILE" /root/.bas-assistant.env

echo "setup_server: OK"
docker --version
docker compose version
swapon --show
ufw status | head -5
