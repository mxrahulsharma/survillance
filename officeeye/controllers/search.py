"""The search box on the Live cameras page: people, phones, vehicles, colours,
and the AI search for anything else."""

from urllib.parse import quote

from flask import Blueprint, jsonify, redirect, request

from officeeye.core import config
from officeeye.services import search
from officeeye.services.sources import pipeline

bp = Blueprint("search", __name__)


@bp.get("/search")
def search_page():
    """The search lives on the Live cameras page."""
    q = request.args.get("q", "")[:100]
    return redirect("/live?q=" + quote(q) if q else "/live")


@bp.get("/api/search")
def api_search():
    """Search the cameras' latest checks (services/search.py). On the cloud
    view the office PC answers (cloud.RELAY_GET)."""
    def answer():
        latest, look = pipeline.latest()
        return search.answer(request.args.get("q", "")[:100], latest, look, config.cameras(),
                             pipeline.class_names(), pipeline.detector("phone")), latest, look

    out, latest, look = answer()
    if out["ok"] and search.stale(latest, look):
        pipeline.look_all(search.FRESH)         # old pictures: looked at again, the answer follows
        out = answer()[0]
    return jsonify(out)


@bp.post("/api/search/check")
def api_search_check():
    """Search -> Check now: every camera is looked at again within a minute or so."""
    pipeline.look_all()
    return jsonify({"ok": True, "message": "Looking at every camera again"})


@bp.post("/api/search/warm")
def api_search_warm():
    """The search box got focus: the AI search model loads meanwhile."""
    search.ai.warm()
    return jsonify({"ok": True})


@bp.post("/api/search/ai")
def api_search_ai_start():
    """The AI search (YOLOE) for words the model does not always look for."""
    body = request.get_json(silent=True) or {}
    words = search.ai_words(str(body.get("q") or ""))
    if not words:
        return jsonify({"ok": False, "message": "Type what to look for"})
    latest, _ = pipeline.latest()
    return jsonify(search.ai.start(str(body.get("q"))[:100], words, latest, config.cameras(), pipeline))


@bp.get("/api/search/ai")
def api_search_ai():
    have = [c for c in (request.args.get("have") or "").split(",") if c]
    return jsonify(search.ai.public(have))
