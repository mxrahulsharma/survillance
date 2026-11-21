"""Parking: the page, its rules and one day's vehicles."""

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from officeeye.controllers.common import day_arg, page
from officeeye.core import cloud, config
from officeeye.models import events
from officeeye.services.sources import manager, pipeline

bp = Blueprint("parking", __name__)


@bp.get("/parking")
def parking_page():
    return page("parking.html", "parking", cameras=manager.listing(config.COUNT))


def _parking_rules_out():
    rules, office = cloud.section("parking"), cloud.section("office")
    return {"rules": rules, "office": {"open": office.get("open"), "close": office.get("close")}}


@bp.get("/api/parking/rules")
def api_parking_rules():
    return jsonify(_parking_rules_out())


@bp.post("/api/parking/rules")
def api_parking_rules_save():
    body = request.get_json(silent=True) or {}
    patch = {}
    try:
        if "arrive_seconds" in body:
            patch["arrive_seconds"] = min(max(float(body["arrive_seconds"]), 10), 600)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "Seconds must be a number"})
    if "enabled" in body:
        patch["enabled"] = bool(body["enabled"])
    if "cameras" in body:
        known = {c["id"] for c in config.cameras(config.COUNT)}
        patch["cameras"] = [str(c) for c in body["cameras"] or [] if str(c) in known][:200]
    config.update("parking", patch)
    pipeline.reload()          # vehicles are looked for only while a camera watches the parking
    return jsonify({"ok": True, "message": "Parking rules saved", **_parking_rules_out()})


@bp.get("/api/parking")
def api_parking():
    """One day at the parking: every vehicle that stood there that day - one
    that came the day before and stayed on too - and what is parked now
    (still open and seen in the last half hour: on a busy PC a quiet parking
    camera is looked at only every few minutes)."""
    day = day_arg()
    first = datetime.strptime(day, "%Y-%m-%d")
    start = first.strftime("%Y-%m-%dT00:00:00")
    end = (first + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
    camera = request.args.get("camera") or None
    rows = events.between(["parking"], (first - timedelta(days=7)).strftime("%Y-%m-%d"), end,
                          camera=camera, limit=5000)
    records = [r for r in rows
               if (r["meta"].get("started") or r["ts"]) < end and
               (r["meta"].get("ended") or r["meta"].get("last_seen") or r["ts"]) >= start]
    now = datetime.now()
    recent = (now - timedelta(minutes=30)).isoformat(timespec="seconds")
    open_rows = events.between(["parking"], (now - timedelta(days=7)).strftime("%Y-%m-%d"), "9999",
                               camera=camera, limit=1000)
    parked = [r for r in open_rows
              if not r["meta"].get("ended") and (r["meta"].get("last_seen") or "") >= recent]
    return jsonify({"day": day, "records": records, "parked": parked, **_parking_rules_out()})
