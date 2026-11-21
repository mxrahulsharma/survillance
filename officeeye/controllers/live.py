"""Live cameras: the camera wall page, each camera's picture, full-rate
video of one camera, and the saved photos."""

import os
import time

from flask import Blueprint, Response, abort, request, send_from_directory
from werkzeug.security import safe_join

from officeeye.controllers.common import page
from officeeye.core import cloud
from officeeye.models import photos
from officeeye.services.frames import blank, render
from officeeye.services.sources import manager

bp = Blueprint("live", __name__)


@bp.get("/live")
def live_page():
    return page("live.html", "live", cameras=manager.listing(),
                query=request.args.get("q", "")[:100])


@bp.get("/frame/<cam_id>.jpg")
def frame_jpg(cam_id):
    """The camera wall polls this - one small request per tile, not a video
    stream per tile (a browser only opens 6 connections to one server)."""
    if cloud.CLOUD:
        return cloud.frame_response(cam_id, blank)
    width = min(int(request.args.get("w", 480)), 1280)
    overlay = request.args.get("overlay", "1") != "0"
    caption = request.args.get("caption", "1") != "0"
    jpg, _ = render(cam_id, width, overlay, quality=70, caption=caption)
    if jpg is None:
        st = manager.get(cam_id)
        text = "no IP set" if st is None or not st.url else "connecting..."
        return Response(blank(text), mimetype="image/jpeg",
                        headers={"Cache-Control": "no-store"})
    return Response(jpg, mimetype="image/jpeg",
                    headers={"Cache-Control": "no-store"})


@bp.get("/snapshot/<cam_id>.jpg")
def snapshot(cam_id):
    return frame_jpg(cam_id)


@bp.get("/live/<cam_id>")
def live(cam_id):
    """Full-rate video of one camera. While it is open the camera decodes
    every frame and is checked more often."""
    if cloud.CLOUD:
        return cloud.live_response(cam_id, blank)
    stream = manager.get(cam_id)
    if stream is None:
        abort(404)
    width = min(int(request.args.get("w", 960)), 1920)

    def gen():
        stream.watch()
        try:
            last, last_sent = None, 0.0
            while manager.get(cam_id) is stream:
                jpg, key = render(cam_id, width, True, quality=78)
                now = time.time()
                if jpg is None:
                    jpg, key = blank("connecting..."), "blank"
                # Re-send now and then even when nothing changed: it is the
                # only way to notice the viewer has gone.
                if key != last or now - last_sent > 2.0:
                    last, last_sent = key, now
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\n"
                           b"Content-Length: " + str(len(jpg)).encode()
                           + b"\r\n\r\n" + jpg + b"\r\n")
                time.sleep(1 / 20.0)
        finally:
            stream.unwatch()

    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame",
                    headers={"Cache-Control": "no-store"})


@bp.get("/photos/<path:name>")
def photo(name):
    path = safe_join(photos.PHOTO_DIR, name)
    if path and os.path.isfile(path):
        return send_from_directory(photos.PHOTO_DIR, name, max_age=86400)
    # Not here: on the cloud view it is still on its way from the office PC,
    # on the office PC it was deleted. A picture saying so - never a broken
    # image - and not cached, so the real photo shows once it arrives.
    text = "photo on its way" if cloud.CLOUD else "photo deleted"
    return Response(blank(text), mimetype="image/jpeg", headers={"Cache-Control": "no-store"})
