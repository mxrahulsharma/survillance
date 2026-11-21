"""Night vision (after-hours watch): the page, its rules and one night's records."""

from datetime import datetime, timedelta

from flask import Blueprint, abort, jsonify, request

from officeeye.controllers.common import HM, page
from officeeye.core import cloud, config
from officeeye.models import events
from officeeye.services import night
from officeeye.services.sources import manager

bp = Blueprint("night", __name__)


@bp.get("/night")
def night_page():
    cams = [c for c in manager.listing() if c.get("group") in night.NightWatch.groups]
    return page("night.html", "night", cameras=cams)


def _night_rules_out():
    rules, office = cloud.section("night"), cloud.section("office")
    return {"rules": rules, "now": night.night_state(rules, office, datetime.now())}


@bp.get("/api/night/rules")
def api_night_rules():
    return jsonify(_night_rules_out())


@bp.post("/api/night/rules")
def api_night_rules_save():
    body = request.get_json(silent=True) or {}
    patch = {}
    try:
        if "motion_every" in body:
            patch["motion_every"] = min(max(float(body["motion_every"]), 1), 60)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "Minutes must be a number"})
    for key in ("watch_from", "watch_to"):
        if key in body:
            v = str(body[key] or "").strip()
            if not HM.match(v):
                return jsonify({"ok": False, "message": "Times look like 20:00"})
            patch[key] = v
    if "enabled" in body:
        patch["enabled"] = bool(body["enabled"])
    if "movement" in body:
        patch["movement"] = bool(body["movement"])
    if body.get("sensitivity") in ("low", "medium", "high"):
        patch["sensitivity"] = body["sensitivity"]
    if "cameras_off" in body:
        known = {c["id"] for c in config.cameras()}
        patch["cameras_off"] = [str(c) for c in body["cameras_off"] or [] if str(c) in known][:200]
    config.update("night", patch)
    return jsonify({"ok": True, "message": "Night rules saved", **_night_rules_out()})


@bp.get("/api/night")
def api_night():
    """One night's records: everything recorded during the watch that began
    on that date - by the hours in force when it was recorded, so changing
    the hours later hides nothing. No date = tonight, or last night before
    the morning end. "from" / "to" are that night's hours as set now."""
    rules, office = cloud.section("night"), cloud.section("office")
    start, end = rules.get("watch_from") or "20:00", rules.get("watch_to") or "08:00"
    day = (request.args.get("night") or "").strip()
    try:
        first = datetime.strptime(day, "%Y-%m-%d") if day else \
            datetime.strptime(night.night_of(rules, office, datetime.now()), "%Y-%m-%d")
    except ValueError:
        abort(400)
    label = first.strftime("%Y-%m-%d")
    last = first + timedelta(days=1 if start > end else 0)
    frm = "{}T{}".format(label, start)
    to = "{}T{}".format(last.strftime("%Y-%m-%d"), end)

    def night_of_row(r):
        # Older records do not carry their night: they go by their time.
        if r["meta"].get("night"):
            return r["meta"]["night"]
        back = start > end and r["ts"][11:16] < end
        return (datetime.strptime(r["ts"][:10], "%Y-%m-%d") - timedelta(days=1 if back else 0)).strftime("%Y-%m-%d")

    rows = events.between(["night_activity"], label, (first + timedelta(days=2)).strftime("%Y-%m-%d"),
                          camera=request.args.get("camera") or None, limit=5000)
    rows = [r for r in rows if night_of_row(r) == label]
    return jsonify({"night": label, "from": frm, "to": to, "events": rows,
                    "cameras": night.detector.cameras(), **_night_rules_out()})
