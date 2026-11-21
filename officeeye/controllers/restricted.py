"""Restricted area: the page and its alerts."""

from flask import Blueprint, abort, jsonify, request

from officeeye.controllers.common import day_arg, page
from officeeye.core import config
from officeeye.models import events, photos
from officeeye.services.sources import manager

bp = Blueprint("restricted", __name__)


@bp.get("/restricted")
def restricted_page():
    return page("restricted.html", "restricted",
                cameras=manager.listing(config.RESTRICTED))


@bp.get("/api/alerts")
def api_alerts():
    limit = min(int(request.args.get("limit", 50)), 500)
    return jsonify({"alerts": events.recent(limit, "restricted_alert",
                                            day=day_arg(),
                                            camera=request.args.get("camera"))})


@bp.get("/api/alerts/<int:event_id>")
def api_alert(event_id):
    ev = events.get(event_id)
    if not ev:
        abort(404)
    return jsonify(ev)


@bp.post("/api/alerts/<int:event_id>/delete")
def api_alert_delete(event_id):
    """Delete one restricted-area alert and its photos (the cloud view and
    the MongoDB copy follow within a minute or two)."""
    meta = events.delete(event_id, "restricted_alert")
    if meta is None:
        return jsonify({"ok": False, "message": "That alert is already gone"})
    photos.remove(meta.get("photos"))
    return jsonify({"ok": True, "message": "Alert deleted"})


@bp.post("/api/alerts/delete")
def api_alerts_delete():
    """Delete several restricted-area alerts and their photos at once
    (Restricted page -> Select)."""
    body = request.get_json(silent=True) or {}
    try:
        ids = [int(i) for i in body.get("ids") or []][:1000]
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "Pick the alerts to delete"})
    gone = 0
    for event_id in ids:
        meta = events.delete(event_id, "restricted_alert")
        if meta is not None:
            photos.remove(meta.get("photos"))
            gone += 1
    return jsonify({"ok": True, "deleted": gone,
                    "message": "{} alert{} deleted".format(gone, "" if gone == 1 else "s")})
