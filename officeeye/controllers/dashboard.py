"""Dashboard: the overview page, the live status every page polls, the
day chart and the notes shown on every page."""

from flask import Blueprint, jsonify, request

from officeeye.controllers.common import day_arg, page
from officeeye.core import cloud
from officeeye.core.version import APP_VERSION
from officeeye.models import events
from officeeye.services.sources import manager
from officeeye.services.status import NOTICE_KINDS, status_payload

bp = Blueprint("dashboard", __name__)


@bp.get("/")
def dashboard():
    return page("dashboard.html", "dashboard", cameras=manager.listing())


@bp.get("/api/status")
def api_status():
    body = cloud.store.status_payload() if cloud.CLOUD else status_payload()
    return jsonify(dict(body, version=APP_VERSION))


@bp.get("/api/notices")
def api_notices():
    """New vehicles and camera problems after id `after`, for the note on every page."""
    rows = events.after_of(NOTICE_KINDS, int(request.args.get("after", 0) or 0))
    return jsonify({"notices": [r for r in rows if not (r["kind"] == "parking" and r["meta"].get("was_there"))]})


@bp.get("/api/people/day")
def api_people_day():
    """People in view hour by hour, for the dashboard chart."""
    out = events.people_by_hour(day_arg())
    office = cloud.section("office")
    out["open"], out["close"] = office.get("open"), office.get("close")
    return jsonify(out)
