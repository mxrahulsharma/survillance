"""Washroom: the page, one day at the washroom doors, and clean / dirty checks."""

from datetime import datetime, timedelta

from flask import Blueprint, abort, jsonify, request

from officeeye.controllers.common import day_arg, page
from officeeye.core import config
from officeeye.models import events
from officeeye.services.sources import manager

bp = Blueprint("washroom", __name__)

WASH_KINDS = ["washroom_visit", "washroom_in", "washroom_out", "washroom_door", "washroom_check"]
WASH_USES = ["washroom_visit", "washroom_in", "washroom_out", "washroom_door"]
PROBLEMS = ("dirty", "damaged")


@bp.get("/washroom")
def washroom_page():
    return page("washroom.html", "washroom", cameras=manager.listing(config.WASHROOM))


@bp.get("/api/washroom")
def api_washroom():
    """One day at the washroom doors: visits, door-only uses and checks."""
    day = day_arg()
    end = (datetime.strptime(day, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    return jsonify({"day": day, "events": events.between(
        WASH_KINDS, day, end, camera=request.args.get("camera") or None)})


@bp.get("/api/washroom/since")
def api_washroom_since():
    """Who went in between the last 'checked clean' and a problem report (or
    now): the people to ask when the washroom is found dirty or damaged."""
    camera = request.args.get("camera") or None
    now = datetime.now().isoformat(timespec="seconds")
    report = request.args.get("at") or None
    if report is not None:
        try:
            report = datetime.fromisoformat(report).isoformat(timespec="seconds")
        except ValueError:
            abort(400)
    else:
        latest = events.between(["washroom_check"], "2000", "9999", camera, PROBLEMS, limit=1)
        clean_after = events.between(["washroom_check"], latest[0]["ts"] if latest else "9999",
                                     "9999", camera, ("clean",), limit=1) if latest else []
        # The newest problem report, unless it was cleaned since.
        report = latest[0]["ts"] if latest and not clean_after else now
    clean = events.between(["washroom_check"], "2000", report, camera, ("clean",), limit=1)
    start = clean[0]["ts"] if clean else \
        (datetime.fromisoformat(report) - timedelta(days=1)).isoformat(timespec="seconds")
    visits = events.between(WASH_USES, start, report + "~", camera, limit=300)
    return jsonify({"from": start, "clean": clean[0] if clean else None, "to": report,
                    "is_report": report != now, "visits": visits})


@bp.post("/api/washroom/check")
def api_washroom_check():
    body = request.get_json(silent=True) or {}
    status = body.get("status")
    cam = config.camera(body.get("camera") or "")
    if status not in ("clean",) + PROBLEMS or not cam:
        return jsonify({"ok": False, "message": "Pick a washroom camera and what was found"})
    eid = events.log("washroom_check", camera=cam["id"], label=status, value=0,
                     meta={"note": str(body.get("note") or "")[:300]})
    return jsonify({"ok": True, "id": eid, "message": {
        "clean": "Marked clean", "dirty": "Marked dirty", "damaged": "Marked damaged"}[status]})
