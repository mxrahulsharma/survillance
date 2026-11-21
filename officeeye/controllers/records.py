"""Records of every kind: the list, and deleting them by hand."""

from flask import Blueprint, jsonify, request

from officeeye.models import events, photos
from officeeye.services import fire, seats

bp = Blueprint("records", __name__)

# Records that can be deleted by hand, photos and all (the trash icon and
# Select on the Phone use, Head down, Night vision, Washroom and Monitoring agent pages).
DELETABLE = ("restricted_alert", "phone_use", "head_down", "night_activity",
             "washroom_visit", "washroom_in", "washroom_out", "washroom_door", "parking",
             "camera_health", fire.KIND, seats.KIND)


@bp.post("/api/records/delete")
def api_records_delete():
    body = request.get_json(silent=True) or {}
    try:
        ids = [int(i) for i in body.get("ids") or []][:1000]
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "Pick the records to delete"})
    gone = 0
    for event_id in ids:
        ev = events.get(event_id)
        if ev and ev["kind"] in DELETABLE:
            meta = events.delete(event_id, ev["kind"])
            if meta is not None:
                photos.remove(meta.get("photos"))
                seats.remove_clip(meta.get("clip"))      # a sitting's clip of the arrival
                gone += 1
    return jsonify({"ok": True, "deleted": gone,
                    "message": "{} record{} deleted".format(gone, "" if gone == 1 else "s")})


@bp.get("/api/events")
def api_events():
    limit = min(int(request.args.get("limit", 50)), 500)
    return jsonify({"events": events.recent(limit, request.args.get("kind"))})
