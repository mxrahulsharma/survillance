"""Cameras: the page, adding / changing / removing cameras, their zones and
ignore areas, and the network scan."""

from flask import Blueprint, abort, jsonify, request

from officeeye.controllers.common import page
from officeeye.core import config
from officeeye.services import scan
from officeeye.services.sources import manager

bp = Blueprint("cameras", __name__)


@bp.get("/cameras")
def cameras_page():
    return page("cameras.html", "cameras", cameras=manager.listing())


@bp.post("/api/cameras/add")
def api_camera_add():
    body = request.get_json(silent=True) or {}
    return jsonify({"ok": True, "camera": manager.add(body.get("group",
                                                              config.COUNT))})


@bp.post("/api/cameras/<cam_id>/save")
def api_camera_save(cam_id):
    body = request.get_json(silent=True) or {}
    ok, message, values = manager.save(cam_id, body.get("ip"), body.get("url"),
                                       body.get("name"), body.get("group"))
    return jsonify({"ok": ok, "message": message, "values": values,
                    "status": manager.status().get(cam_id, {})})


@bp.post("/api/cameras/<cam_id>/zone")
def api_camera_zone(cam_id):
    if config.camera(cam_id) is None:
        abort(404)
    body = request.get_json(silent=True) or {}
    zone = manager.set_zone(cam_id, body.get("zone"))
    return jsonify({"ok": True, "zone": zone,
                    "message": "Zone saved" if zone else
                               "No zone - the whole picture is watched"})


@bp.post("/api/cameras/<cam_id>/ignore")
def api_camera_ignore(cam_id):
    if config.camera(cam_id) is None:
        abort(404)
    body = request.get_json(silent=True) or {}
    shapes = manager.set_ignore(cam_id, body.get("ignore"))
    return jsonify({"ok": True, "ignore": shapes,
                    "message": "{} ignore area{} saved".format(
                        len(shapes), "" if len(shapes) == 1 else "s")})


@bp.post("/api/cameras/<cam_id>/reset")
def api_camera_reset(cam_id):
    values = manager.reset(cam_id)
    return jsonify({"ok": True, "message": "Cleared", "values": values,
                    "status": manager.status().get(cam_id, {})})


@bp.post("/api/cameras/<cam_id>/remove")
def api_camera_remove(cam_id):
    manager.remove(cam_id)
    return jsonify({"ok": True, "message": "Camera removed"})


@bp.post("/api/scan")
def api_scan_start():
    started = scan.scanner.start()
    return jsonify({
        "ok": started,
        "message": "Scanning the network..." if started
                   else "A scan is already running",
        "scan": scan.scanner.public(),
    })


@bp.get("/api/scan")
def api_scan_status():
    return jsonify(scan.scanner.public())


@bp.post("/api/scan/add")
def api_scan_add():
    body = request.get_json(silent=True) or {}
    ok, message, values = manager.add_scanned(body.get("ip"),
                                              body.get("group", config.COUNT))
    return jsonify({"ok": ok, "message": message, "values": values})


@bp.post("/api/scan/add-all")
def api_scan_add_all():
    body = request.get_json(silent=True) or {}
    added = manager.add_all_scanned(body.get("group", config.COUNT))
    return jsonify({"ok": True, "added": added,
                    "message": "Added {} camera{}".format(
                        len(added), "" if len(added) == 1 else "s")})
