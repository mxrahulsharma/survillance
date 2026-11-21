"""Camera pictures as JPEG for the pages: the newest frame with the boxes
drawn, and a grey picture with a word on it when there is none."""

import threading

import cv2
import numpy as np

from officeeye.services.sources import manager, pipeline

_jpeg_cache = {}            # (camera, width, overlay) -> (key, bytes)
_jpeg_lock = threading.Lock()


def render(cam_id, width, overlay=True, quality=75, caption=True):
    """Newest frame of a camera as JPEG, with the boxes drawn. Encoded once
    per new frame or new result, however many people are looking."""
    stream = manager.get(cam_id)
    if stream is None:
        return None, None
    frame, _, seq = stream.latest()
    if frame is None:
        return None, None
    key = (seq, pipeline.version(cam_id) if overlay else 0)
    ck = (cam_id, width, overlay, caption)
    with _jpeg_lock:
        hit = _jpeg_cache.get(ck)
        if hit and hit[0] == key:
            return hit[1], key
    img = frame.copy()
    if overlay:
        img = pipeline.overlay(cam_id, img, caption)
    if width and img.shape[1] > width:
        scale = width / float(img.shape[1])
        img = cv2.resize(img, None, fx=scale, fy=scale,
                         interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return None, None
    jpg = buf.tobytes()
    with _jpeg_lock:
        _jpeg_cache[ck] = (key, jpg)
    return jpg, key


def _placeholder(text="no signal"):
    img = np.full((360, 480, 3), 30, dtype="uint8")
    (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
    cv2.putText(img, text, ((480 - tw) // 2, 190), cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (130, 130, 130), 2, cv2.LINE_AA)
    ok, buf = cv2.imencode(".jpg", img)
    return buf.tobytes() if ok else b""


_BLANK = {}


def blank(text):
    if text not in _BLANK:
        _BLANK[text] = _placeholder(text)
    return _BLANK[text]
