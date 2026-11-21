#!/usr/bin/env bash
# OfficeEye + NetraAttend - set up / update the server (Ubuntu VPS).
# Run on the server inside the project folder:   bash deploy/vps_install.sh
# First run creates .env from .env.example - fill it in (nano .env) and run again.
#
# PROXY=caddy  (default) this project's Caddy serves https on ports 80/443.
# PROXY=apache the server's existing Apache serves https: the app listens on
#              127.0.0.1:APP_PORT and an Apache site for DOMAIN forwards to it.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker"
  curl -fsSL https://get.docker.com | sudo sh
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo
  echo "Created .env - fill it in now:   nano .env   then run this script again."
  exit 0
fi
if grep -q "change-me" .env; then
  echo "Fill in .env first (it still contains 'change-me'):   nano .env"
  exit 1
fi

env_value() { grep "^$1=" .env | tail -n1 | cut -d= -f2- | tr -d '\r' || true; }
domain=$(env_value DOMAIN)
proxy=$(env_value PROXY); proxy=${proxy:-caddy}
app_port=$(env_value APP_PORT); app_port=${app_port:-8800}

if [ "$proxy" = "apache" ]; then
  if ss -tlnp | grep -E ":${app_port} " | grep -qv docker; then
    echo "Port ${app_port} is already used by another program - set APP_PORT in .env to a free port."
    exit 1
  fi

  echo "==> Building and starting the app (Apache in front, no Caddy)"
  sudo docker compose up -d --build app
  sudo docker compose stop caddy >/dev/null 2>&1 || true

  site="/etc/apache2/sites-available/${domain}.conf"
  echo "==> Apache site ${site}"
  sudo a2enmod proxy proxy_http headers >/dev/null
  if [ ! -f "$site" ]; then
    sed -e "s/__DOMAIN__/${domain}/g" -e "s/__APP_PORT__/${app_port}/g" \
      deploy/apache-site.conf | sudo tee "$site" >/dev/null
    sudo a2ensite "${domain}.conf" >/dev/null
  else
    echo "    (exists - left as it is)"
  fi
  if sudo apache2ctl configtest; then
    sudo systemctl reload apache2
  else
    echo "Apache config test failed - nothing reloaded. Check ${site}."
    exit 1
  fi

  sudo docker compose ps app
  echo
  if [ ! -f "/etc/letsencrypt/live/${domain}/fullchain.pem" ]; then
    echo "HTTPS certificate (once):"
    echo "    sudo apt install -y certbot python3-certbot-apache"
    echo "    sudo certbot --apache -d ${domain}"
    echo
  fi
else
  echo "==> Building and starting OfficeEye + NetraAttend (with Caddy)"
  sudo docker compose up -d --build
  sudo docker compose ps
  echo
fi

echo "Done. In a minute or two open:  https://${domain}             (OfficeEye)"
echo "                                https://${domain}/attendance  (attendance)"
echo "Logs:                           sudo docker compose logs -f app"
