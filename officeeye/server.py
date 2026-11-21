"""Start-up: one copy only, the background jobs, the cameras and detection,
then the web server on PORT (8000)."""

import logging
import os
import threading

# The services, in this order: importing a detector adds it to the detection
# pipeline (washroom, head down, night, parking, seats).
from officeeye.core import access  # noqa: F401
from officeeye.core import cloud
from officeeye.core import config
from officeeye.models import events  # noqa: F401
from officeeye.models import mongo
from officeeye.models import photos
from officeeye.services import scan  # noqa: F401
from officeeye.services import washroom  # noqa: F401 - adds its detection to the pipeline
from officeeye.services import sleeping  # noqa: F401 - head down / sleeping, added the same way
from officeeye.services import night  # noqa: F401 - night watch after office hours, the same way
from officeeye.services import parking  # noqa: F401 - cars and bikes in the parking, the same way
from officeeye.services import search  # noqa: F401 - the search box: people, phones, vehicles, any object
from officeeye.services import push                         # phone alerts for the installed app (PWA)
from officeeye.services import health                       # camera health: offline, covered, moved, blurry
from officeeye.services import fire                         # fire and smoke on every camera
from officeeye.services import seats  # noqa: F401 - who sits at each seat, with a clip of each arrival
from officeeye.services.sources import manager, pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("werkzeug").setLevel(logging.WARNING)   # one line per image is noise
log = logging.getLogger("app")

PORT = int(os.environ.get("PORT", 8000))      # Render and the like set PORT

from officeeye import create_app  # noqa: E402
from officeeye.controllers import attendance  # noqa: E402
from officeeye.services import housekeeping  # noqa: E402
from officeeye.services.frames import render  # noqa: E402
from officeeye.services.status import status_payload  # noqa: E402

app = create_app()


def _already_running(port):
    """Windows lets a second process bind the same port, and then half the
    requests go to the wrong app. Refuse to start instead."""
    import socket
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


_LOCK = None


def _only_copy():
    """One app per data folder. A second copy on another port (a preview, a
    second window) would check every camera twice - on this PC each one then
    waits far longer - and write every record twice."""
    global _LOCK
    os.makedirs(config.DATA_DIR, exist_ok=True)
    f = open(os.path.join(config.DATA_DIR, "app.lock"), "a+")
    try:
        f.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return False
    _LOCK = f
    return True


def main():
    if _already_running(PORT):
        log.error("port %s is already in use - the app is probably open in "
                  "another window. Close it first.", PORT)
        return
    if not cloud.CLOUD and not _only_copy():
        log.error("OfficeEye is already running from this folder (on another port) - "
                  "close that copy first.")
        return
    os.makedirs(photos.PHOTO_DIR, exist_ok=True)
    threading.Thread(target=housekeeping.housekeeping, name="housekeeping", daemon=True).start()
    attendance.mount(app)
    if cloud.CLOUD:
        log.info("cloud view: showing what the office PC sends, on port %s", PORT)
        app.run(host="0.0.0.0", port=PORT, threaded=True, debug=False, use_reloader=False)
        return
    manager.start()
    pipeline.start()
    threading.Thread(target=housekeeping.uptime_watch, name="uptime", daemon=True).start()
    cloud.uplink.start(status_payload, render, manager.listing)
    mongo.sync.start(manager.listing)
    push.sender.start()                 # phone alerts for new alerts and night records
    health.monitor.start(manager)       # every camera's picture, twice a minute
    fire.watch.start(manager, pipeline)  # fire and smoke, every camera about once a minute
    log.info("open  http://localhost:%s", PORT)
    try:
        app.run(host="0.0.0.0", port=PORT, threaded=True,
                debug=False, use_reloader=False)
    finally:
        pipeline.stop()
        manager.stop()
