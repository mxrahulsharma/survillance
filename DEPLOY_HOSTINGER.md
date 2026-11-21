# Deploy OfficeEye on the Hostinger VPS at netraai.itsybizz.com

Server: Hostinger VPS `62.72.23.1`, Ubuntu 22.04, **Apache already serves other
websites on ports 80/443**. So the project's own Caddy is not used here: the app
runs in Docker on `127.0.0.1:8800`, and Apache forwards `netraai.itsybizz.com`
to it (HTTPS from Let's Encrypt via certbot). `deploy/vps_install.sh` does the
Docker and Apache part when `.env` has `PROXY=apache`.

```
Office PC (cameras) --push--> https://netraai.itsybizz.com
                              VPS: Apache :443 -> 127.0.0.1:8800 -> Docker app :8000
                                                                     |
                                                          MongoDB Atlas (office_eye)
```

GitHub repo: `https://github.com/mxrahulsharma/survillance` (keep it **Private**).

---

## Part 1 - DNS (done)

hPanel -> Domains -> itsybizz.com -> DNS / Nameservers: `A` record, name
`netraai`, value `62.72.23.1`. Check: `nslookup netraai.itsybizz.com` -> 62.72.23.1.

---

## Part 2 - Prepare the VPS (once)

```bash
ssh root@62.72.23.1
apt update && apt install -y git curl
```

Firewall: in hPanel -> VPS -> **Firewall**, ports 80 and 443 must be allowed
(they already are, since the other websites work). Don't turn on `ufw` on this
server without checking what else it serves - it would block every port not
listed.

Swap (only if `free -h` shows no swap; the first build installs PyTorch):

```bash
fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

---

## Part 3 - Get the code from GitHub

The repo is private, so give the VPS a read-only **deploy key**:

```bash
ssh-keygen -t ed25519 -C "vps" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
```

Copy the printed line -> GitHub repo -> **Settings -> Deploy keys -> Add deploy key**
(leave "Allow write access" off). Then:

```bash
cd /opt
git clone git@github.com:mxrahulsharma/survillance.git
cd survillance
```

(answer `yes` to the GitHub host fingerprint question)

---

## Part 4 - Configure and start

```bash
bash deploy/vps_install.sh     # 1st run: installs Docker, creates .env, stops
nano .env                      # fill in the values below, Ctrl+O Enter, Ctrl+X
bash deploy/vps_install.sh     # 2nd run: builds (10-20 min first time), starts, adds the Apache site
```

`.env`:

```ini
DOMAIN=netraai.itsybizz.com
PROXY=apache
APP_PORT=8800

OFFICEEYE_USER=admin
OFFICEEYE_PASSWORD=<view-only password for the website>
OFFICEEYE_EDIT_USER=editor
OFFICEEYE_EDIT_PASSWORD=<edit password - changes ask for it>
OFFICEEYE_PUSH_TOKEN=<long random string - the office PC uses it>
OFFICEEYE_SECRET=<long random string>

MONGO_URI=mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/office_eye
NETRA_SECRET_KEY=<long random string>
NETRA_ADMIN_USER=admin
NETRA_ADMIN_PASSWORD=<strong password>
NETRA_ADMIN_LAN_ONLY=False
```

Random strings: `openssl rand -hex 32` (the script refuses to start while any
value is still `change-me`).

**MongoDB Atlas -> Network Access -> Add IP Address -> `62.72.23.1`.**

What the 2nd run does with `PROXY=apache`:
- starts only the `app` container, reachable only from the server at `127.0.0.1:8800`
  (no Caddy, so the other websites on 80/443 are untouched);
- enables Apache's `proxy`, `proxy_http`, `headers` modules;
- writes `/etc/apache2/sites-available/netraai.itsybizz.com.conf` from
  `deploy/apache-site.conf` (only if it doesn't exist yet), enables it, and reloads
  Apache only if `apache2ctl configtest` passes.

### HTTPS certificate (once)

```bash
apt install -y certbot python3-certbot-apache
certbot --apache -d netraai.itsybizz.com
```

Choose "redirect" if asked. Certbot renews it automatically.

---

## Part 5 - Check and connect the office PC

- Open **https://netraai.itsybizz.com** (OfficeEye) and
  **https://netraai.itsybizz.com/attendance/** (attendance).
- Health check: `curl https://netraai.itsybizz.com/healthz`
- Office PC OfficeEye -> **Settings -> Cloud view**: server link
  `https://netraai.itsybizz.com` and the same `OFFICEEYE_PUSH_TOKEN`.

Useful commands on the VPS (inside `/opt/survillance`):

```bash
sudo docker compose ps app           # is the app up?
sudo docker compose logs -f app      # app logs
curl -I http://127.0.0.1:8800/healthz   # app answers locally?
tail -f /var/log/apache2/netraai.itsybizz.com-error.log
sudo docker compose restart app      # restart
```

**Updating later:** push from the PC (`git add -A; git commit -m "..."; git push`),
then on the VPS:

```bash
cd /opt/survillance && git pull && bash deploy/vps_install.sh
```

---

## On an empty server instead

With nothing on ports 80/443, set `PROXY=caddy` in `.env`: the script then also
starts the project's Caddy container, which gets the HTTPS certificate by itself
(no Apache, no certbot).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `503 Service Unavailable` from Apache | App not up yet / crashed: `sudo docker compose logs app`, `curl -I http://127.0.0.1:8800/healthz` |
| Shows one of the other websites | Apache site not enabled: `a2ensite netraai.itsybizz.com.conf && systemctl reload apache2`; check `apache2ctl -S` |
| Certificate error | Run certbot (Part 4); DNS must point to 62.72.23.1 |
| Live camera view stuck | `deploy/apache-site.conf` needs `flushpackets=on` on `ProxyPass` (it has it) - re-create the site file if it was edited |
| "Port 8800 is already used" | Set `APP_PORT` to a free port in `.env`, and the same port in `/etc/apache2/sites-available/netraai.itsybizz.com.conf` |
| Build killed / out of memory | Add the swap from Part 2 |
| App starts but no data / login errors | `MONGO_URI` wrong, or 62.72.23.1 not allowed in Atlas Network Access |
| `git clone` permission denied | Deploy key not added to the repo (Part 3) |
