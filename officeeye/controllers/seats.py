"""Monitoring agent (seats): the page, the seats, sittings and their clips."""

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from officeeye.controllers.common import page
from officeeye.core import config
from officeeye.models import events
from officeeye.services import seats
from officeeye.services.sources import manager

bp = Blueprint("seats", __name__)


@bp.get("/seats")
def seats_page():
    return page("seats.html", "seats", cameras=manager.listing(config.COUNT))


@bp.get("/api/seats")
def api_seats():
    """The seats, who sits at them now, and the sittings of one day (the
    Monitoring agent page). On the cloud view the office PC answers."""
    try:
        d = datetime.strptime(request.args.get("day", ""), "%Y-%m-%d")
    except ValueError:
        d = datetime.now()
    day, nxt = d.strftime("%Y-%m-%d"), (d + timedelta(days=1)).strftime("%Y-%m-%d")
    # A sitting that began the day before and went on into this day counts too.
    prev = (d - timedelta(days=1)).strftime("%Y-%m-%d")
    rows = [r for r in events.between([seats.KIND], prev, nxt, limit=5000)
            if r["day"] == day or (r["meta"].get("end") or r["meta"].get("last") or "") >= day]
    return jsonify({"day": day, "seats": config.get(seats.SECTION), "now": seats.detector.now(),
                    "rules": seats.rules(), "sittings": rows})


@bp.post("/api/seats/rules")
def api_seats_rules():
    """The Monitoring agent's Settings tab: cameras on or off, the timings."""
    body = request.get_json(silent=True) or {}
    patch = seats.clean_rules(body, [c["id"] for c in config.cameras(config.COUNT)])
    config.update(seats.RULES, patch)
    return jsonify({"ok": True, "rules": seats.rules(), "message": "Settings saved"})


@bp.post("/api/seats/<cam_id>")
def api_seats_save(cam_id):
    if config.camera(cam_id) is None:
        return jsonify({"ok": False, "message": "No such camera"})
    body = request.get_json(silent=True) or {}
    kept = seats.clean_seats(body.get("seats"))
    config.update(seats.SECTION, {cam_id: kept})
    on = seats.rules()["cameras"]
    if kept and cam_id not in on:                   # seats drawn: the camera is watched
        config.update(seats.RULES, {"cameras": on + [cam_id]})
    return jsonify({"ok": True, "seats": kept,
                    "message": "Saved: {} seat{}".format(len(kept), "" if len(kept) == 1 else "s")})


@bp.post("/api/seats/clip/delete")
def api_seats_clip_delete():
    """Delete only the clip of a sitting; the record and its photos stay."""
    body = request.get_json(silent=True) or {}
    try:
        ev = events.get(int(body.get("id")))
    except (TypeError, ValueError):
        ev = None
    if not ev or ev["kind"] != seats.KIND or not ev["meta"].get("clip"):
        return jsonify({"ok": False, "message": "That clip is already gone"})
    seats.remove_clip(ev["meta"]["clip"])
    events.update_meta(ev["id"], {"clip": None})
    return jsonify({"ok": True, "message": "Clip deleted"})


@bp.get("/api/seats/suggest")
def api_seats_suggest():
    """Seat boxes from the chairs and people the last check of a camera saw."""
    return jsonify({"seats": seats.suggest(request.args.get("camera", ""))})
