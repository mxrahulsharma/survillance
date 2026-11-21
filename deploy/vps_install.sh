#!/usr/bin/env bash
# OfficeEye + NetraAttend - set up / update the server (Ubuntu VPS).
# Run on the server inside the OfficeEye folder:   bash deploy/vps_install.sh
# First run creates .env from .env.example - fill it in (nano .env) and run again.
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

echo "==> Building and starting OfficeEye + NetraAttend"
sudo docker compose up -d --build
sudo docker compose ps
domain=$(grep '^DOMAIN=' .env | cut -d= -f2)
echo
echo "Done. In a minute or two open:  https://${domain}             (OfficeEye)"
echo "                                https://${domain}/attendance  (attendance)"
echo "Logs:                           sudo docker compose logs -f app"
