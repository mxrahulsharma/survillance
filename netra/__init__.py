"""NetraAttend - CCTV face recognition attendance - as part of OfficeEye.

OfficeEye serves it at /attendance in its own process (create_web_app): the
"web" role - website, employee panel, field attendance and the API. The CCTV
camera and the face matching stay with the NetraAttend running on the office
PC, exactly as before; both use the same MongoDB database.

On its own, as before (port 5000, camera included):   py -3.12 -m netra

Settings: netra/config.py, overridden by NETRA_<NAME> environment variables
(or lines in OfficeEye's .env) - NETRA_MONGO_URI, NETRA_MONGO_DB,
NETRA_ADMIN_PASSWORD, NETRA_SECRET_KEY, ... Inside OfficeEye the MongoDB link
defaults to OfficeEye's own MONGO_URI and its database, so one database holds
both: OfficeEye's collections (cameras, detections, camera_uptime_*) and
NetraAttend's (employees, face_samples, attendance, events, photos, ...).
"""

import logging
import os
import secrets
import threading
import time
from urllib.parse import urlsplit

log = logging.getLogger("netra")

PREFIX = "/attendance"
# NetraAttend's admin menu, for OfficeEye's sidebar: (path inside PREFIX, label)
NAV = [("/", "Dashboard"), ("/live", "Live camera"), ("/employees", "Employees"), ("/reports", "Reports"),
       ("/requests", "Requests"), ("/field", "Field work"), ("/photos", "Photos"), ("/unknown", "Unknown"),
       ("/settings", "Settings")]
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACEHOLDERS = {"SECRET_KEY": "change-me-to-a-long-random-string", "ADMIN_PASSWORD": "change-me"}


def load_env(path=os.path.join(BASE_DIR, ".env")):
    """KEY=value lines of the .env next to OfficeEye into the environment;
    what is set already wins."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    except OSError:
        pass


def create_web_app(admin=None):
    """NetraAttend's website as a WSGI app for OfficeEye to serve at PREFIX.
    It starts in the background (database, face models); until then its pages
    say so. Without NETRA_MONGO_URI it uses OfficeEye's MONGO_URI and that
    link's database (the part after the host) unless NETRA_MONGO_DB is set.
    admin(environ) -> True: OfficeEye already let this person in, so they are
    the admin here without a second login."""
    load_env()
    os.environ.setdefault("NETRA_ROLE", "web")
    uri = os.environ.get("NETRA_MONGO_URI") or os.environ.get("MONGO_URI")
    if uri:
        os.environ.setdefault("NETRA_MONGO_URI", uri)
        name = urlsplit(uri).path.strip("/")
        if name:
            os.environ.setdefault("NETRA_MONGO_DB", name)
    if os.environ.get("NETRA_SECRET_KEY", "") in ("", PLACEHOLDERS["SECRET_KEY"]):
        # app.secret_key is read when the module loads: never the example's placeholder
        os.environ["NETRA_SECRET_KEY"] = secrets.token_hex(32)
        log.warning("NETRA_SECRET_KEY is not set - logins to /attendance end on every restart")

    from . import app as web
    from . import config

    if str(getattr(config, "ADMIN_PASSWORD", "")) in ("", PLACEHOLDERS["ADMIN_PASSWORD"]):
        # never the example's "change-me" on a server on the internet
        config.ADMIN_PASSWORD = secrets.token_urlsafe(32)
        log.warning("NETRA_ADMIN_PASSWORD is not set - the attendance admin login stays closed")
    # Its own cookie, only for /attendance: OfficeEye's "session" cookie on the
    # same site is never overwritten (and the other way round).
    web.app.config.update(SESSION_COOKIE_NAME="netra_session", SESSION_COOKIE_PATH=PREFIX)

    state = {"ready": False}

    def start():
        while True:
            try:
                web.start()
                state["ready"] = True
                log.info("attendance (NetraAttend) ready at %s - database %s", PREFIX, config.MONGO_DB)
                return
            except Exception as exc:                    # noqa: BLE001 - e.g. MongoDB not reachable yet
                log.error("attendance could not start (%s) - trying again in 30 s",
                          type(exc).__name__)
                time.sleep(30)

    threading.Thread(target=start, name="netra-start", daemon=True).start()

    def wsgi(environ, start_response):
        if not state["ready"]:
            start_response("503 Service Unavailable", [("Content-Type", "text/html; charset=utf-8"),
                                                       ("Retry-After", "10")])
            return [b"<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=10>"
                    b"<title>Attendance</title><p style='font-family:system-ui;margin:40px'>"
                    b"Attendance is starting - this page reloads by itself.</p>"]
        environ["netra.officeeye_admin"] = bool(admin and admin(environ))
        return web.app.wsgi_app(environ, start_response)

    return wsgi
