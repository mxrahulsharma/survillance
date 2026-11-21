"""The installed app (PWA): its service worker, and phone alerts (push)."""

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from officeeye.services import push

bp = Blueprint("push", __name__)


@bp.get("/sw.js")
def service_worker():
    """The app's service worker (PWA), served from the top so it covers every page."""
    resp = send_from_directory(current_app.static_folder, "sw.js", mimetype="application/javascript", max_age=0)
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


@bp.get("/api/push/key")
def api_push_key():
    """The key a browser needs to turn on phone alerts (services/push.py)."""
    return jsonify({"key": push.sender.public_key(), "phones": push.sender.phones()})


@bp.post("/api/push/subscribe")
def api_push_subscribe():
    body = request.get_json(silent=True) or {}
    sub = push.sender.subscribe(body.get("subscription"), body.get("device"))
    if not sub:
        return jsonify({"ok": False, "message": "This browser gave no push address"})
    n = push.sender.send({"title": "OfficeEye", "url": "/", "tag": "welcome",
                          "body": "Phone alerts are on - restricted-area and night alerts will show here."},
                         only=sub)
    return jsonify({"ok": True, "phones": push.sender.phones(),
                    "message": "Phone alerts on" if n else
                    "Phone alerts on, but the first test alert could not be sent"})


@bp.post("/api/push/unsubscribe")
def api_push_unsubscribe():
    body = request.get_json(silent=True) or {}
    push.sender.unsubscribe(str(body.get("endpoint") or ""))
    return jsonify({"ok": True, "message": "Phone alerts off on this device",
                    "phones": push.sender.phones()})


@bp.post("/api/push/test")
def api_push_test():
    n = push.sender.send({"title": "OfficeEye test", "url": "/", "tag": "test",
                          "body": "This is how an alert will look."})
    return jsonify({"ok": bool(n), "message": "Test alert sent to {} phone(s)".format(n)})
