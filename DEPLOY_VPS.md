# OfficeEye + NetraAttend on one server (VPS)

OfficeEye (cameras, detections) and NetraAttend (face recognition attendance)
are one app now: one folder, one container, one service, one MongoDB database.

```
                         ONE SERVER (VPS, https)
OFFICE PC                ┌───────────────────────────────────────┐
 OfficeEye (cameras) ───>│ /             OfficeEye cloud view     │
 NetraAttend (camera)    │ /attendance   NetraAttend website, API │
        │                └───────────────────────────────────────┘
        └──────> MongoDB Atlas, database office_eye  <──────┘
                 (OfficeEye: cameras, detections, camera_uptime_*;
                  NetraAttend: employees, face_samples, attendance, events, photos, ...)
```

- One login: OfficeEye's sidebar has an **Attendance** menu (Dashboard, Live
  camera, Employees, Reports, Requests, Field work, Photos, Unknown, Settings);
  its pages open in the same window and whoever is logged in to OfficeEye is the
  attendance admin there - no second login.
  - Office PC: Settings -> Login - a view username/password (look only) and an
    edit username/password (change things too); Sign out at the bottom of the sidebar.
  - Server: the login in its `.env` (`OFFICEEYE_USER`, `OFFICEEYE_PASSWORD`). It can
    change things too - a change made there is made by the office PC.
  Data stays apart: NetraAttend's collections and OfficeEye's, one database.
  Employees still use `https://SERVER/attendance/` with their own login (field
  attendance, leave).
- NetraAttend's API moves to `https://SERVER/attendance/api/v1/...` (docs at
  `/attendance/api/docs`). No API key existed at the merge, so nothing outside breaks.
- On the office PC nothing changes: OfficeEye on port 8000, NetraAttend on
  port 5000 (its own service - it needs the CPU first so nobody walks past
  unseen). The cameras never go to the server.
- Code: NetraAttend is the `netra/` folder (`py -3.12 -m netra` runs it on its
  own, as before). OfficeEye serves it at /attendance when
  `OFFICEEYE_ATTENDANCE=on` (docker-compose.yml sets it).

## Switch-over (do these together, e.g. in the evening)

**Steps 1 and 2 were done on 19 Nov 2026, 15:16:** the office PC's NetraAttend
and OfficeEye write and read `office_eye`; `netraattend` is no longer written
(kept as a backup). Only the server steps (3-5) are left.

1. **Copy the attendance data a last time** (on the office PC, OfficeEye folder):
   `py -3.12 tools/merge_netra_db.py` - the copy in `office_eye` becomes exactly
   `netraattend` (employees, registered faces, attendance, leaves, settings...).
   `netraattend` is only read and stays as a backup.
2. **Office PC NetraAttend -> the same database:** in its `config.py` set
   `MONGO_DB = "office_eye"`, then restart its service (deploy\INSTALL.bat).
   From now on attendance goes to `office_eye`. In OfficeEye's `.env` delete the
   line `NETRA_MONGO_DB=netraattend` and restart OfficeEye: its Attendance menu
   then reads `office_eye` too.
3. **Server** (Ubuntu, 2 GB RAM or more; the domain's DNS pointing at it; ports
   80 and 443 open in the provider's firewall): put the OfficeEye folder on it -
   `git clone https://github.com/amit-sharma-ds/OfficeEye.git` or the zip - then
   inside it
   ```bash
   bash deploy/vps_install.sh     # 1st run: installs Docker, creates .env
   nano .env                      # DOMAIN, passwords, MONGO_URI (.../office_eye)
   bash deploy/vps_install.sh     # 2nd run: builds and starts
   ```
   MongoDB Atlas -> Network Access: allow the server's IP.
4. **Office PC OfficeEye -> the server:** Settings -> Cloud view: the server's
   link and its push token (`OFFICEEYE_PUSH_TOKEN` in .env).
5. Check `https://SERVER/` and `https://SERVER/attendance/`, then the old Render
   services (officeeye, netraattend) can be suspended.

The office PC's NetraAttend uses `DET_WIDTH = 640` (the server copy only checks
selfies and uploaded photos and keeps 960, as on Render).

## What goes on the server

The whole folder; the image takes what it needs (`.dockerignore` keeps `.env`,
`data/`, models, zips and logs out of it).

```
OfficeEye/
  docker-compose.yml   the two containers: app (OfficeEye + attendance) and caddy (https)
  Dockerfile           how the app image is built (Python 3.12, CPU PyTorch, face models)
  .env.example         -> .env on the server: domain, logins, MONGO_URI (never in git)
  deploy/              Caddyfile (https for DOMAIN), vps_install.sh (install / update)
  app.py               the start (python app.py)
  officeeye/           OfficeEye: controllers/, services/, models/, core/, templates/, static/
                       (ARCHITECTURE.md; core/cloud.py: the server side, core/access.py: the office PC login)
  netra/               NetraAttend (attendance) at /attendance
  tools/               office PC tools (database copy, login reset)
  render.yaml, run.bat Render and the office PC only - not used on the server
```

## Later

- Update: `git pull` (or copy the new folder over the old one), then `bash deploy/vps_install.sh`.
- Logs: `sudo docker compose logs -f app` - restart: `sudo docker compose restart`.
