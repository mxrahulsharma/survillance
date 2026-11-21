"""Settings store. Everything lives in data/config.json so the app can be
reconfigured from the browser without touching the code or restarting."""

import json
import os
import threading
from copy import deepcopy

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # the project folder (this file: officeeye/core/)
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

# What a camera is there for. Counting cameras feed the Person count page;
# restricted cameras watch an area nobody should be in and raise alerts.
COUNT = "count"
RESTRICTED = "restricted"
WASHROOM = "washroom"     # outside a washroom door: who went in and out (washroom.py)
GROUPS = (COUNT, RESTRICTED, WASHROOM)

DEFAULTS = {
    # As many cameras as the office needs. Each one is
    # {"id": "cam1", "name": "Camera 1", "group": "count",
    #  "ip": "...", "url": "rtsp://...",
    #  "zone": [[x, y], ...],      restricted only: 0-1 fractions of the picture
    #  "ignore": [[[x, y], ...]]}  areas never counted: posters, TVs, mannequins
    "cameras": [],
    "office": {
        "open": "09:30",
        "close": "18:30",
        "late_after": "09:45",
        "timezone": "Asia/Kolkata",
    },
    "detection": {
        "enabled": True,
        "confidence": 0.3,        # low on purpose: ceiling cameras see people
        "model": "yolo26s.pt",    # at odd angles; the count smoother and ignore
                                  # areas keep false boxes out
        "device": "auto",         # auto = the NVIDIA GPU when there is one
        "imgsz": 480,             # model input: 320 fast, 480 balanced, 640 sharpest
        "phone": True,            # look for phones as well as people
        "count_refresh": 30,      # re-check a quiet counting camera at least this often (s)
        "restricted_fps": 4,      # most checks per second for one restricted camera
    },
    "photos": {
        "keep_days": 30,
    },
    # Phone-use rules (Phone use page -> Rules & timing).
    "phone": {
        "min_seconds": 10,        # use must last this long to count - not a touch
        "watch_from": "",         # "" = when the office opens
        "watch_to": "",           # "" = when it closes
        "breaks": [],             # [["13:00", "14:00"], ...] phones allowed, not recorded
        "photo_every": 2,         # minutes between photos from one camera
        "sensitivity": "medium",  # low / medium / high
    },
    # Head down / sleeping rules (Sleeping page -> Rules & timing, sleeping.py).
    "sleeping": {
        "min_minutes": 5,         # still with the head down this long to count
        "watch_from": "",         # "" = when the office opens
        "watch_to": "",           # "" = when it closes
        "breaks": [],             # [["13:00", "14:00"], ...] not recorded
    },
    # Night watch (Night vision page, night.py): after the office has closed.
    "night": {
        "enabled": True,
        "watch_from": "20:00",    # the night runs past midnight ...
        "watch_to": "08:00",      # ... to this time next morning
        "movement": False,        # also movement and lights records - at night insects at
                                  # the lens, car lights and dawn set these off, not people
        "sensitivity": "medium",  # movement: low / medium / high
        "motion_every": 5,        # minutes between movement records from one camera
        "cameras_off": [],        # camera ids the night watch leaves out
    },
    # Parking (Parking page, parking.py): cars and bikes on the cameras that see it.
    "parking": {
        "enabled": True,
        "cameras": [],            # camera ids that look at the parking
        "arrive_seconds": 20,     # standing at one spot this long = a new vehicle (alert), not passing by
    },
    # Fire and smoke (Fire & smoke page, fire.py): every camera, day and night.
    "fire": {
        "enabled": True,
        "smoke": True,            # alert for smoke too, not only flames
        "sensitivity": "medium",  # low / medium / high: how sure the model has to be
        "cameras_off": [],        # camera ids left out (a kitchen stove in view, say)
    },
    # A copy of every record in MongoDB (mongo.py). The connection string is
    # MONGO_URI in the .env file - never here, never in the repository.
    "mongodb": {
        "enabled": True,          # copies whenever MONGO_URI is set
    },
    # Send what the office sees to the cloud view (cloud.py). The token is
    # the shared secret; the cloud host gets the same one as OFFICEEYE_PUSH_TOKEN.
    "cloud": {
        "enabled": False,
        "url": "",
        "token": "",
    },
}

_lock = threading.RLock()
# The settings are kept as JSON text, and every read gets its own fresh copy
# of just what it asks for (json.loads). A deepcopy of the whole file took
# ~3 ms of pure Python - holding every other thread up - and it ran on every
# frame of a washroom camera and every check of a restricted one: the web
# pages stalled for seconds. Same copies as before, a small part of the cost.
_text = None            # all settings, as JSON text
_parts = {}             # ("section", name) / ("camera", id) / ("cameras",) -> JSON text


def _keep(cfg):
    global _text
    _text = json.dumps(cfg)
    _parts.clear()


def _part(key, pick):
    """A fresh copy of one part of the settings."""
    with _lock:
        if _text is None:
            load()
        text = _parts.get(key)
        if text is None:
            text = _parts[key] = json.dumps(pick(json.loads(_text)))
        return json.loads(text)


def _merge(base, extra):
    out = deepcopy(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load(force=False):
    with _lock:
        if _text is not None and not force:
            return json.loads(_text)
        raw = {}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
            except (OSError, ValueError):
                raw = {}
        _keep(_merge(DEFAULTS, _migrate(raw)))
        return json.loads(_text)


def _migrate(raw):
    """Older versions stored a fixed camera_in / camera_out pair."""
    if not raw.get("cameras") and ("camera_in" in raw or "camera_out" in raw):
        cams = []
        for key in ("camera_in", "camera_out"):
            old = raw.pop(key, None) or {}
            if old.get("url"):
                n = len(cams) + 1
                cams.append({"id": "cam{}".format(n), "name": "Camera {}".format(n),
                             "ip": old.get("ip", ""), "url": old["url"]})
        raw["cameras"] = cams
    raw.pop("camera_in", None)
    raw.pop("camera_out", None)
    for cam in raw.get("cameras") or []:
        cam.setdefault("group", COUNT)
    # "fps" was a per-camera detection rate; the scheduler decides that now.
    (raw.get("detection") or {}).pop("fps", None)
    return raw


def save(cfg):
    with _lock:
        merged = _merge(DEFAULTS, cfg)
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=2)
        os.replace(tmp, CONFIG_PATH)
        _keep(merged)
        return json.loads(_text)


def update(section, values):
    """Patch one section (e.g. 'office') and write the file."""
    with _lock:
        cfg = load()
        cfg[section] = _merge(cfg.get(section, {}), values)
        return save(cfg)


def get(section):
    return _part(("section", section), lambda cfg: cfg.get(section, {}))


# ---------------------------------------------------------------- cameras

def cameras(group=None):
    items = _part(("cameras",), lambda cfg: cfg.get("cameras", []))
    if group is None:
        return items
    return [c for c in items if c.get("group", COUNT) == group]


def camera_group(cam_id):
    cam = camera(cam_id)
    return (cam or {}).get("group", COUNT)


def set_cameras(items):
    with _lock:
        cfg = load()
        cfg["cameras"] = list(items)
        return save(cfg)


def camera(cam_id):
    return _part(("camera", cam_id),
                 lambda cfg: next((c for c in cfg.get("cameras", []) if c.get("id") == cam_id), None))


def next_camera_id():
    used = {c.get("id") for c in cameras()}
    n = 1
    while f"cam{n}" in used:
        n += 1
    return f"cam{n}"
