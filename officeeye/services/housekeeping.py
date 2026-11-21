"""Background jobs of the web app: hourly clean-up, and the camera running
time (how long each camera was connected)."""

import logging
import time
from datetime import datetime

from officeeye.core import config
from officeeye.models import events, photos
from officeeye.services.sources import manager

log = logging.getLogger("app")


def housekeeping():
    """Once an hour: drop old events and old photos."""
    while True:
        try:
            events.purge_older_than(90)
            photos.purge(config.get("photos").get("keep_days", 30))
        except Exception:                                   # noqa: BLE001
            log.exception("housekeeping failed")
        time.sleep(3600)


def uptime_watch(every=10, flush=60):
    """How long each camera is connected: its state is looked at every few
    seconds and added up per hour, written once a minute. Cameras with no IP
    yet are left out; time the app itself is not running counts as neither."""
    was_up, pending, closed_for = {}, {}, None
    last = last_flush = time.time()
    while True:
        time.sleep(every)
        now = time.time()
        span = min(now - last, 3 * every)        # PC asleep: don't count the gap
        last = now
        stamp = datetime.now()
        try:
            status = manager.status()
            for cam_id, st in status.items():
                if st.get("state") == "off":
                    was_up.pop(cam_id, None)
                    continue
                up = st.get("state") == "connected"
                key = (stamp.strftime("%Y-%m-%d"), stamp.hour, cam_id)
                row = pending.setdefault(key, [0.0, 0.0, 0, None])
                row[0 if up else 1] += span
                if was_up.get(cam_id) and not up:
                    row[2] += 1
                if up:
                    row[3] = stamp.isoformat(timespec="seconds")
                was_up[cam_id] = up
            if now - last_flush >= flush:
                events.add_uptime([k + tuple(v) for k, v in pending.items()])
                pending, last_flush = {}, now
                day = stamp.strftime("%Y-%m-%d")
                if closed_for != day:             # first flush of a new day
                    saved = events.close_days(day, {k: v["name"] for k, v in status.items()})
                    if saved:
                        log.info("daily camera running time saved for %s", ", ".join(saved))
                    closed_for = day
        except Exception:                                   # noqa: BLE001
            log.exception("uptime watch failed")
