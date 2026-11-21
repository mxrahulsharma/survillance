"""Phone use: the page, its rules and the day's records."""

import json
import os
from datetime import datetime

from flask import Blueprint, jsonify, request

from officeeye.controllers.common import HM, day_arg, page
from officeeye.core import cloud, config
from officeeye.models import events
from officeeye.services.detection import phone_watch_state
from officeeye.services.sources import manager, pipeline

bp = Blueprint("phone", __name__)


@bp.get("/phone")
def phone_page():
    return page("phone.html", "phone", cameras=manager.listing(config.COUNT))


def _phone_model():
    """The office-trained phone model: in use, or what its last test said."""
    folder = os.path.join(config.DATA_DIR, "phone")
    out = {}
    for name in ("model", "report"):
        try:
            with open(os.path.join(folder, name + ".json"), encoding="utf-8") as f:
                out[name] = json.load(f)
        except (OSError, ValueError):
            pass
    return out


def _phone_rules_out():
    rules, office = cloud.section("phone"), cloud.section("office")
    return {"rules": rules, "office": {"open": office.get("open"), "close": office.get("close")},
            "now": phone_watch_state(rules, office, datetime.now()), "model": _phone_model()}


@bp.get("/api/phone/rules")
def api_phone_rules():
    return jsonify(_phone_rules_out())


@bp.post("/api/phone/rules")
def api_phone_rules_save():
    body = request.get_json(silent=True) or {}
    patch = {}
    try:
        if "min_seconds" in body:
            patch["min_seconds"] = min(max(int(body["min_seconds"]), 0), 600)
        if "photo_every" in body:
            patch["photo_every"] = min(max(float(body["photo_every"]), 0), 120)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "Seconds and minutes must be numbers"})
    for key in ("watch_from", "watch_to"):
        if key in body:
            v = str(body[key] or "").strip()
            if v and not HM.match(v):
                return jsonify({"ok": False, "message": "Times look like 09:30"})
            patch[key] = v
    if "breaks" in body:
        breaks = []
        for b in body["breaks"] or []:
            if not (isinstance(b, (list, tuple)) and len(b) == 2 and all(HM.match(str(x)) for x in b)):
                return jsonify({"ok": False, "message": "Each break needs a start and an end, like 13:00 - 14:00"})
            breaks.append([str(b[0]), str(b[1])])
        patch["breaks"] = breaks
    if body.get("sensitivity") in ("low", "medium", "high"):
        patch["sensitivity"] = body["sensitivity"]
    config.update("phone", patch)
    pipeline.reload()
    return jsonify({"ok": True, "message": "Phone rules saved", **_phone_rules_out()})


@bp.get("/api/phone/uses")
def api_phone_uses():
    """Every phone use of a day: from when to when, with a photo when one
    was taken. (Older records only have photos.)"""
    rows = events.recent(1000, "phone_use", day=day_arg(),
                         camera=request.args.get("camera") or None)
    uses = [r for r in rows if r["meta"].get("started") or r["meta"].get("photos")]
    return jsonify({"uses": uses, "seconds": sum(r["meta"].get("seconds") or 0 for r in uses)})


@bp.get("/api/phone")
def api_phone():
    limit = min(int(request.args.get("limit", 60)), 500)
    return jsonify({"events": events.recent(limit, "phone_use", day=day_arg(),
                                            camera=request.args.get("camera"),
                                            with_photos=True)})
