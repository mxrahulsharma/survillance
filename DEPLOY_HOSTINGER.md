# Deploy OfficeEye on a Hostinger VPS at survillance.itsybizz.com

The project already ships with everything the server needs:
`Dockerfile` (the app), `docker-compose.yml` (app + Caddy), `deploy/Caddyfile`
(free automatic HTTPS) and `deploy/vps_install.sh` (install / update).
This guide is the exact path: **PC -> GitHub -> Hostinger VPS -> subdomain**.

```
Office PC (cameras)  --push-->  https://survillance.itsybizz.com  (VPS: Docker -> Caddy -> app:8000)
                                         |
                                  MongoDB Atlas (office_eye)
```

---

## Part 1 - Push the code to GitHub (on your Windows PC)

1. On github.com: **New repository** -> name `OfficeEye` -> **Private** -> do NOT
   add a README/.gitignore (the project has them) -> Create.
2. In PowerShell, inside `D:\ai_project\OfficeEye`:
   ```powershell
   git remote add origin https://github.com/<your-user>/OfficeEye.git
   git branch -M main
   git push -u origin main
   ```
   (The first push opens a browser window to sign in to GitHub.)

`.gitignore` already keeps `.env`, `data/`, models, logs and zips out of GitHub -
never commit `.env`.

---

## Part 2 - Point the subdomain at the VPS (Hostinger hPanel)

1. hPanel -> **VPS** -> your server -> copy its **IPv4 address**.
2. hPanel -> **Domains** -> `itsybizz.com` -> **DNS / Nameservers** -> **Add record**:

   | Type | Name          | Points to       | TTL |
   |------|---------------|-----------------|-----|
   | A    | `survillance` | `<VPS IPv4>`    | 300 |

3. Wait 5-30 minutes, then check from your PC:
   ```powershell
   nslookup survillance.itsybizz.com
   ```
   It must answer with the VPS IP **before** you start the app (the HTTPS
   certificate is issued for this name on first start).

---

## Part 3 - Prepare the VPS (once)

Recommended: Ubuntu 22.04/24.04, **at least 2 GB RAM** (4 GB+ is comfortable;
the build installs PyTorch).

1. hPanel -> VPS -> **Firewall**: allow TCP **22, 80, 443** (or leave the
   Hostinger firewall off and use ufw below).
2. Connect from PowerShell (root password / SSH key from hPanel -> VPS -> Overview):
   ```powershell
   ssh root@<VPS IPv4>
   ```
3. On the VPS:
   ```bash
   apt update && apt upgrade -y
   apt install -y git curl ufw
   ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable

   # Swap, so the Docker build does not run out of memory on small VPS plans
   fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
   echo '/swapfile none swap sw 0 0' >> /etc/fstab
   ```
4. **Check that nothing else uses ports 80/443** (e.g. a Hostinger template with
   Nginx/Apache/CyberPanel):
   ```bash
   ss -tlnp | grep -E ':80 |:443 '
   ```
   Empty output = good, continue. If something is listed, see **Part 7**.

---

## Part 4 - Get the code from GitHub onto the VPS

The repo is private, so give the VPS a read-only **deploy key**:

```bash
ssh-keygen -t ed25519 -C "officeeye-vps" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
```

Copy the printed line -> GitHub repo -> **Settings -> Deploy keys -> Add deploy key**
(title `vps`, leave "Allow write access" off) -> Add. Then:

```bash
cd /opt
git clone git@github.com:<your-user>/OfficeEye.git
cd OfficeEye
```

---

## Part 5 - Configure and start

```bash
bash deploy/vps_install.sh     # 1st run: installs Docker, creates .env, stops
nano .env                      # fill in the values below, Ctrl+O Enter, Ctrl+X
bash deploy/vps_install.sh     # 2nd run: builds and starts (10-20 min first time)
```

`.env` values:

```ini
DOMAIN=survillance.itsybizz.com

OFFICEEYE_USER=admin
OFFICEEYE_PASSWORD=<strong password for the website>
OFFICEEYE_PUSH_TOKEN=<long random string - the office PC uses it>
OFFICEEYE_SECRET=<long random string>

MONGO_URI=mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/office_eye
NETRA_SECRET_KEY=<long random string>
NETRA_ADMIN_USER=admin
NETRA_ADMIN_PASSWORD=<strong password>
NETRA_ADMIN_LAN_ONLY=False
```

Make random strings on the VPS with: `openssl rand -hex 32`
(the script refuses to start while any value is still `change-me`).

**MongoDB Atlas -> Network Access -> Add IP Address -> the VPS IPv4.**

---

## Part 6 - Check and connect the office PC

- Open **https://survillance.itsybizz.com** (OfficeEye) and
  **https://survillance.itsybizz.com/attendance/** (attendance).
- Health check: `curl https://survillance.itsybizz.com/healthz`
- Office PC OfficeEye -> **Settings -> Cloud view**: server link
  `https://survillance.itsybizz.com` and the same `OFFICEEYE_PUSH_TOKEN`.

Useful commands on the VPS (inside `/opt/OfficeEye`):

```bash
sudo docker compose ps               # are both containers up?
sudo docker compose logs -f app      # app logs
sudo docker compose logs caddy       # HTTPS / certificate problems
sudo docker compose restart          # restart
```

**Updating later:** push from the PC (`git add -A; git commit -m "..."; git push`),
then on the VPS:

```bash
cd /opt/OfficeEye && git pull && bash deploy/vps_install.sh
```

---

## Part 7 - Only if ports 80/443 are already used on the VPS

If the VPS already serves other sites with Nginx, don't run Caddy; let Nginx proxy
the subdomain to the app instead.

1. In `docker-compose.yml`, under `app:` replace `expose: - "8000"` with
   ```yaml
       ports:
         - "127.0.0.1:8000:8000"
   ```
   and start only the app: `sudo docker compose up -d --build app`
2. `/etc/nginx/sites-available/survillance.itsybizz.com`:
   ```nginx
   server {
       server_name survillance.itsybizz.com;
       client_max_body_size 50M;
       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_read_timeout 300;
       }
   }
   ```
3. Enable it and get HTTPS:
   ```bash
   ln -s /etc/nginx/sites-available/survillance.itsybizz.com /etc/nginx/sites-enabled/
   nginx -t && systemctl reload nginx
   apt install -y certbot python3-certbot-nginx
   certbot --nginx -d survillance.itsybizz.com
   ```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Browser shows certificate error | DNS wasn't pointing at the VPS when Caddy started: check `nslookup`, then `sudo docker compose restart caddy` |
| Build killed / out of memory | Add the swap from Part 3, or a bigger VPS plan |
| App starts but no data / login errors | `MONGO_URI` wrong, or VPS IP not allowed in Atlas Network Access |
| `git clone` permission denied | Deploy key not added to the repo (Part 4) |
| Site not reachable at all | Hostinger firewall / ufw must allow 80 and 443 |
