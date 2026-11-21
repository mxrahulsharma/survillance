"""Fire and smoke: the page, its rules, records and the photo test."""

from datetime import datetime, timedelta

import cv2
import numpy as np
from flask import Blueprint, jsonify, request

from officeeye.controllers.common import page
from officeeye.core import cloud, config
from officeeye.models import events
from officeeye.services import fire
from officeeye.services.sources import manager

bp = Blueprint("fire", __name__)


@bp.get("/fire")
def fire_page():
    return page("fire.html", "fire", cameras=manager.listing())


def _fire_out():
    rules = cloud.section("fire")
    return dict(fire.watch.report(rules), rules=rules)


@bp.get("/api/fire")
def api_fire():
    """Fire and smoke on every camera now, and the records of the last 30 days."""
    since = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    return jsonify(dict(_fire_out(), records=events.between([fire.KIND], since, "9999", limit=300)))


@bp.post("/api/fire/rules")
def api_fire_rules_save():
    body = request.get_json(silent=True) or {}
    patch = {}
    for key in ("enabled", "smoke"):
        if key in body:
            patch[key] = bool(body[key])
    if body.get("sensitivity") in fire.SURE:
        patch["sensitivity"] = body["sensitivity"]
    if "cameras_off" in body:
        known = {c["id"] for c in config.cameras()}
        patch["cameras_off"] = [str(c) for c in body["cameras_off"] or [] if str(c) in known][:200]
    config.update("fire", patch)
    return jsonify(dict(_fire_out(), ok=True, message="Fire and smoke rules saved"))


@bp.post("/api/fire/<int:event_id>/not-fire")
def api_fire_not_fire(event_id):
    ok = fire.watch.not_fire(event_id)
    return jsonify({"ok": ok, "message": "Thanks - this spot will not alert again" if ok
                    else "Record not found"})


@bp.post("/api/fire/spots/forget")
def api_fire_spots_forget():
    camera = str((request.get_json(silent=True) or {}).get("camera") or "") or None
    n = fire.watch.forget_spots(camera)
    return jsonify({"ok": True, "message": "Forgot {} learnt spot{}".format(n, "" if n == 1 else "s")})


@bp.post("/api/fire/test")
def api_fire_test():
    """A photo sent from the page: what would the fire check say about it?"""
    data = str((request.get_json(silent=True) or {}).get("image") or "")
    try:
        import base64
        raw = base64.b64decode(data.split(",", 1)[-1][:16_000_000])
        frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    except (ValueError, TypeError):
        frame = None
    if frame is None:
        return jsonify({"ok": False, "message": "That is not a picture"})
    found = fire.watch.test(frame)
    if found is None:
        return jsonify({"ok": False, "message": "The fire model is not running"})
    return jsonify({"ok": True, "found": found})
