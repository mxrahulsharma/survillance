"""Head down (sleeping): the page, its rules and the day's records."""

from datetime import datetime

from flask import Blueprint, jsonify, request

from officeeye.controllers.common import HM, day_arg, page
from officeeye.core import cloud, config
from officeeye.models import events
from officeeye.services import sleeping
from officeeye.services.sources import manager

bp = Blueprint("sleeping", __name__)


@bp.get("/sleeping")
def sleeping_page():
    return page("sleeping.html", "sleeping", cameras=manager.listing(config.COUNT))


def _sleep_rules_out():
    rules, office = cloud.section("sleeping"), cloud.section("office")
    return {"rules": rules, "office": {"open": office.get("open"), "close": office.get("close")},
            "now": sleeping.watch_state(rules, office, datetime.now())}


@bp.get("/api/sleeping/rules")
def api_sleeping_rules():
    return jsonify(_sleep_rules_out())


@bp.post("/api/sleeping/rules")
def api_sleeping_rules_save():
    body = request.get_json(silent=True) or {}
    patch = {}
    try:
        if "min_minutes" in body:
            patch["min_minutes"] = min(max(float(body["min_minutes"]), 1), 120)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "Minutes must be a number"})
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
    config.update("sleeping", patch)
    return jsonify({"ok": True, "message": "Rules saved", **_sleep_rules_out()})


@bp.get("/api/sleeping/uses")
def api_sleeping_uses():
    """Every head-down spell of a day: from when to when, with a photo."""
    uses = events.recent(1000, "head_down", day=day_arg(),
                         camera=request.args.get("camera") or None)
    return jsonify({"uses": uses, "seconds": sum(r["meta"].get("seconds") or 0 for r in uses)})
