#!/usr/bin/env bash
# Run on the destination server, from its checkout. No root password is stored.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
SOURCE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN="${1:-}"
if [[ -n "$DOMAIN" && ! "$DOMAIN" =~ ^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$ ]]; then
  echo 'Invalid domain'; exit 1
fi
apt-get update
apt-get install -y python3 rsync
id beerhappy >/dev/null 2>&1 || useradd --system --home-dir /var/lib/beerhappy --shell /usr/sbin/nologin beerhappy
install -d -o root -g root /opt/beerhappy
install -d -o beerhappy -g beerhappy -m 700 /var/lib/beerhappy
rsync -a --exclude .git --exclude data --exclude .env --exclude __pycache__ "$SOURCE_DIR/" /opt/beerhappy/
if [[ ! -f /etc/beerhappy.env ]]; then
  install -m 600 /opt/beerhappy/.env.example /etc/beerhappy.env
fi
if [[ -n "$DOMAIN" ]]; then
  apt-get install -y nginx certbot python3-certbot-nginx
  # Unique virtual host; never overwrite other sites or remove their defaults.
  cat > /etc/nginx/sites-available/beerhappy <<EOF
server {
  listen 80;
  server_name $DOMAIN;
  client_max_body_size 32k;
  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host \$host;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_read_timeout 35s;
  }
}
EOF
  ln -sfn /etc/nginx/sites-available/beerhappy /etc/nginx/sites-enabled/beerhappy
  nginx -t
  systemctl reload nginx
  # Interactive contact/terms prompts stay visible to the server owner.
  certbot --nginx -d "$DOMAIN" --redirect
  sed -i "s|^PUBLIC_URL=.*|PUBLIC_URL=https://$DOMAIN|" /etc/beerhappy.env
fi
install -m 644 /opt/beerhappy/deploy/beerhappy.service /etc/systemd/system/beerhappy.service
systemctl daemon-reload
systemctl enable --now beerhappy
systemctl restart beerhappy
for attempt in 1 2 3 4 5; do
  if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=2)" 2>/dev/null; then
    echo 'Beerhappy is healthy.'
    if [[ -z "$DOMAIN" ]]; then
      echo 'Local mode: use SSH forwarding. No public HTTP login is enabled.'
    else
      echo "Open https://$DOMAIN"
    fi
    exit 0
  fi
  sleep 1
done
journalctl -u beerhappy -n 20 --no-pager
exit 1
