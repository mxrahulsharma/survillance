"""Login on the office PC (its local and network link): a username and
password to look (View), and a separate username and password to change
things too (Edit) - settings, cameras, rules, deleting records, and the
attendance (employees, entries, its settings). Off until both are set in
Settings -> Login; then every page asks for a username and password first,
and which one was typed decides. The cloud view keeps its own login (cloud.py).

Forgot them? On the office PC: py -3.12 tools/reset_login.py, then restart.
"""

import hashlib
import hmac
import os
import secrets
import time
from datetime import timedelta
from urllib.parse import quote, urlsplit

from flask import jsonify, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from officeeye.core import config

SECTION = "access"
VIEW, EDIT = "view", "edit"
EDIT_ONLY = "You are logged in to view only. Log in with the edit username and password to change this."
MIN_LEN = 6
# Posts that only look, or set up this device's phone alerts: a View login may.
VIEW_POSTS = ("/api/search/", "/api/push/")
RELAY = "officeeye.relay"          # set by cloud.py on a change made on the cloud view
_failures = {}                     # ip -> [times of wrong passwords]


def _cfg():
    return config.get(SECTION) or {}


def enabled():
    c = _cfg()
    return bool(c.get("view_user") and c.get("view_hash") and c.get("edit_user") and c.get("edit_hash"))


def _key(c):
    """Sessions are tied to the current passwords: a new one logs everybody out."""
    return hashlib.sha256((c.get("view_hash", "") + "|" + c.get("edit_hash", "")).encode()).hexdigest()[:16]


def role():
    """This browser: EDIT, VIEW or None (not logged in). Login off: EDIT."""
    c = _cfg()
    if not enabled():
        return EDIT
    if session.get("acc") != _key(c):
        return None
    return session.get("role") if session.get("role") in (VIEW, EDIT) else None


def _sign_in(r):
    session.clear()
    session["acc"] = _key(_cfg())
    session["role"] = r
    session.permanent = True


def _safe_next(nxt):
    return nxt if nxt and nxt.startswith("/") and not nxt.startswith("//") else "/"


def _wants_page(environ):
    return "text/html" in environ.get("HTTP_ACCEPT", "")


def _in_officeeye(path):
    """An attendance page comes back inside OfficeEye's window, under its sidebar."""
    if path == "/attendance" or path.startswith("/attendance/"):
        return "/attendance-app?p=" + quote(path[len("/attendance"):] or "/", safe="/")
    return path


def check(environ, path):
    """What the login allows for one request: None (go ahead), "login" (log
    in first) or "edit" (needs the edit login). Used for OfficeEye's own pages
    and for the attendance pages mounted next to them."""
    if not enabled() or environ.get(RELAY):
        return None
    r = role()
    if r is None:
        return "login"
    if r == VIEW and environ.get("REQUEST_METHOD", "GET") not in ("GET", "HEAD") \
            and not path.startswith(VIEW_POSTS):
        return "edit"
    return None


def refusal(why, environ, full_path):
    """The answer to a request check() did not allow."""
    if why == "login":
        if _wants_page(environ) and environ.get("REQUEST_METHOD", "GET") in ("GET", "HEAD"):
            return redirect("/login?next=" + quote(_in_officeeye(full_path)))
        return jsonify({"ok": False, "msg": "Log in first", "message": "Log in first", "login": True}), 401
    if _wants_page(environ):
        # a form sent with the view login (the attendance pages): the edit login,
        # then back to the page it came from
        ref = urlsplit(environ.get("HTTP_REFERER", ""))
        back = _safe_next(_in_officeeye(ref.path + ("?" + ref.query if ref.query else "")) if ref.path else "/")
        return redirect("/login?edit=1&next=" + quote(back))
    return jsonify({"ok": False, "msg": EDIT_ONLY, "message": EDIT_ONLY, "edit_login": True}), 403


def _secret():
    """Signs the login cookie; kept in data/ so logins survive a restart."""
    path = os.path.join(config.DATA_DIR, "session.key")
    try:
        with open(path, encoding="ascii") as fh:
            key = fh.read().strip()
        if len(key) >= 32:
            return key
    except OSError:
        pass
    key = secrets.token_hex(32)
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="ascii") as fh:
        fh.write(key)
    return key


def install(app):
    """Office PC only (the cloud view has its own login)."""
    if not app.secret_key:
        app.secret_key = _secret()
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      PERMANENT_SESSION_LIFETIME=timedelta(days=30))

    @app.context_processor
    def _login_state():
        return {"login_on": enabled(), "login_role": role() if enabled() else None}

    @app.before_request
    def _gate():
        p = request.path
        if p in ("/login", "/logout", "/sw.js", "/favicon.ico") or p.startswith("/static/"):
            return None
        if p.startswith("/api/access") and request.environ.get(RELAY):
            return jsonify({"ok": False, "message": "The login is changed on the office PC."}), 403
        why = check(request.environ, p)
        return refusal(why, request.environ, request.full_path.rstrip("?")) if why else None

    @app.route("/login", methods=["GET", "POST"])
    def login():
        nxt = _safe_next(request.values.get("next"))
        if not enabled():
            return redirect(nxt)
        error = ""
        want_edit = bool(request.values.get("edit"))
        if request.method == "POST":
            ip = request.remote_addr or ""
            now = time.time()
            recent = [t for t in _failures.get(ip, []) if now - t < 600]
            c = _cfg()
            user = request.form.get("username", "").strip().lower()
            typed = request.form.get("password", "")
            got = None                      # the edit login, else the view login
            for r, name, pw_hash in ((EDIT, c["edit_user"], c["edit_hash"]),
                                     (VIEW, c["view_user"], c["view_hash"])):
                if hmac.compare_digest(user.encode(), str(name).lower().encode()) \
                        and check_password_hash(pw_hash, typed):
                    got = r
                    break
            if len(recent) >= 10:
                error = "Too many wrong passwords. Try again in a few minutes."
            elif got:
                _failures.pop(ip, None)
                _sign_in(got)
                return redirect(nxt)
            else:
                time.sleep(1)
                _failures[ip] = recent + [now]
                error = "Wrong username or password."
        return render_template("login.html", error=error, next=nxt, local_login=True, want_edit=want_edit)

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect("/login")

    @app.get("/api/access")
    def access_get():
        c = _cfg()
        mine = role() == EDIT
        return jsonify({"on": enabled(), "view_user": c.get("view_user", "") if mine else "",
                        "edit_user": c.get("edit_user", "") if mine else "", "role": role()})

    @app.post("/api/access")
    def access_save():
        """Set or change the login (the edit login only, once it is on).
        Blank password = keep the one there is."""
        body = request.get_json(silent=True) or {}
        c = _cfg()
        view_user = str(body.get("view_user") or "").strip() or c.get("view_user", "")
        view_pw = str(body.get("view_password") or "")
        edit_user = str(body.get("edit_user") or "").strip() or c.get("edit_user", "")
        edit_pw = str(body.get("edit_password") or "")
        on = enabled()
        if not on and not (view_user and view_pw and edit_user and edit_pw):
            return jsonify({"ok": False, "message": "Fill in all four: the view username and password, "
                                                    "and the edit username and password."})
        if not view_user or not edit_user:
            return jsonify({"ok": False, "message": "The usernames cannot be empty."})
        for pw, name in ((view_pw, "view"), (edit_pw, "edit")):
            if pw and len(pw) < MIN_LEN:
                return jsonify({"ok": False, "message": "The %s password needs at least %d characters." % (name, MIN_LEN)})
        if view_pw and edit_pw and view_pw == edit_pw:
            return jsonify({"ok": False, "message": "The view and edit passwords have to be different."})
        if view_pw and on and not edit_pw and check_password_hash(c["edit_hash"], view_pw):
            return jsonify({"ok": False, "message": "The view and edit passwords have to be different."})
        if edit_pw and on and not view_pw and check_password_hash(c["view_hash"], edit_pw):
            return jsonify({"ok": False, "message": "The view and edit passwords have to be different."})
        patch = {"view_user": view_user, "edit_user": edit_user}
        if view_pw:
            patch["view_hash"] = generate_password_hash(view_pw)
        if edit_pw:
            patch["edit_hash"] = generate_password_hash(edit_pw)
        config.update(SECTION, patch)
        _sign_in(EDIT)                     # whoever set it stays in, as the editor
        return jsonify({"ok": True, "message": "Saved - the login is on. Everybody else logs in again."
                        if on else "Saved - the login is on. Other devices now see the login page.",
                        "on": True, "view_user": view_user, "edit_user": edit_user, "role": EDIT})

    @app.post("/api/access/off")
    def access_off():
        cfg = config.load()
        cfg.pop(SECTION, None)
        config.save(cfg)
        return jsonify({"ok": True, "message": "The login is off - anybody on the office network can open and change everything.",
                        "on": False, "role": EDIT})
