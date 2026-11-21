"""Camera health: the page, each camera's health now and its normal view."""

from datetime import datetime, timedelta

from flask import Blueprint, abort, jsonify, send_file

from officeeye.controllers.common import page
from officeeye.models import events
from officeeye.services import health
from officeeye.services.sources import manager

bp = Blueprint("health", __name__)


@bp.get("/health")
def health_page():
    return page("health.html", "health", cameras=manager.listing(), states=health.STATES)


@bp.get("/api/health")
def api_health():
    """Each camera's health now, and the problems of the last 7 days."""
    since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    return jsonify(dict(health.monitor.report(),
                        history=events.between([health.KIND], since, "9999", limit=500)))


@bp.post("/api/health/<cam_id>/normal")
def api_health_normal(cam_id):
    ok = health.monitor.accept_view(cam_id)
    return jsonify({"ok": ok, "message": "Saved: this is its normal view now" if ok
                    else "No picture from this camera right now"})


@bp.get("/health/normal/<cam_id>.jpg")
def health_normal(cam_id):
    path = health.monitor.normal_view(cam_id)
    if not path:
        abort(404)
    return send_file(path, mimetype="image/jpeg", max_age=0)
