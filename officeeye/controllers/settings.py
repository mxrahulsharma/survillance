"""Settings: the page, office timing, detection, photos and the MongoDB copy.
(The login card is core/access.py, the cloud view card core/cloud.py.)"""

import os

from flask import Blueprint, jsonify, request

from officeeye.controllers.common import page
from officeeye.core import cloud, config
from officeeye.models import mongo, photos
from officeeye.services.sources import pipeline

bp = Blueprint("settings", __name__)

# Detection models offered on Settings, best first. Measured 2026-10-19 on 34
# frames from the office cameras (18 people): yolo26s found 13, yolo26n-objv1
# 9, yolo11n 7. Other .pt files dropped in the folder (a trained model) are
# listed after these.
MODELS = [
    ("yolo26s.pt", "YOLO26s - most accurate, finds about twice the people (recommended)"),
    ("yolo26n-objv1-150.pt", "YOLO26n Objects365 - fast, a little better than YOLO11n"),
    ("yolo26n.pt", "YOLO26n - fastest"),
    ("yolo11n.pt", "YOLO11n - the old default"),
    ("yolo11s.pt", "YOLO11s"),
]


def _models():
    """The known models (one not on disk yet downloads itself when chosen),
    then any other .pt in the project folder."""
    base = config.BASE_DIR
    extra = sorted(f for f in os.listdir(base)
                   if f.endswith(".pt") and f not in dict(MODELS))
    return MODELS + [(f, f) for f in extra]


@bp.get("/settings")
def settings_page():
    return page("settings.html", "settings", models=_models(),
                office=cloud.section("office"),
                detection=cloud.section("detection"),
                keep_days=cloud.section("photos").get("keep_days", 30))


@bp.post("/api/office")
def api_office():
    body = request.get_json(silent=True) or {}
    keep = {k: body[k] for k in ("open", "close", "late_after", "timezone")
            if k in body}
    cfg = config.update("office", keep)
    return jsonify({"ok": True, "message": "Office timing saved",
                    "office": cfg["office"]})


@bp.post("/api/detection")
def api_detection():
    body = request.get_json(silent=True) or {}
    patch = {}
    for key in ("enabled", "phone"):
        if key in body:
            patch[key] = bool(body[key])
    limits = {"confidence": (0.1, 0.95), "count_refresh": (5, 600),
              "restricted_fps": (0.5, 15)}
    for key, (lo, hi) in limits.items():
        if key in body:
            try:
                patch[key] = min(max(float(body[key]), lo), hi)
            except (TypeError, ValueError):
                pass
    if body.get("imgsz") in (320, 416, 480, 640, "320", "416", "480", "640"):
        patch["imgsz"] = int(body["imgsz"])
    if body.get("model") in dict(_models()):
        patch["model"] = body["model"]
    config.update("detection", patch)
    pipeline.reload()
    return jsonify({"ok": True, "message": "Detection settings saved",
                    "detection": pipeline.status()})


@bp.post("/api/photos")
def api_photos():
    body = request.get_json(silent=True) or {}
    try:
        days = min(max(int(body.get("keep_days", 30)), 1), 3650)
    except (TypeError, ValueError):
        days = 30
    config.update("photos", {"keep_days": days})
    gone = photos.purge(days)
    return jsonify({"ok": True, "keep_days": days,
                    "message": "Saved - photos kept for {} days".format(days)
                               + (" ({} old day(s) cleared)".format(gone) if gone else "")})


@bp.get("/api/photos/usage")
def api_photos_usage():
    files, mb = photos.usage()
    return jsonify({"files": files, "mb": mb})


@bp.get("/api/mongo")
def api_mongo():
    """How far the MongoDB copy of the records has got."""
    return jsonify(mongo.sync.info())
