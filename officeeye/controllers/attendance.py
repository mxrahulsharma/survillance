"""Attendance: NetraAttend (face recognition attendance, netra/) in this same
process at /attendance - its own pages and data, next to OfficeEye's, under
OfficeEye's sidebar. On with OFFICEEYE_ATTENDANCE=on (docker-compose.yml on a
server; .env on the office PC: its website part only - the camera and face
matching keep their own process on port 5000, they need the CPU first)."""

import logging
import os

from flask import Blueprint, abort, current_app, request

from officeeye.controllers.common import page
from officeeye.core import access, cloud
from officeeye.models import mongo

log = logging.getLogger("app")

bp = Blueprint("attendance", __name__)


def _attendance_on():
    mongo._load_env()                   # .env is read here, after start-up
    return os.environ.get("OFFICEEYE_ATTENDANCE", "off").lower() in ("1", "on", "true", "yes")


def _office_network(addr):
    """The request comes from the office network: this PC, or another device on
    the same network (its local link, 192.168.x.x) - not from the internet."""
    import ipaddress
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


def mount(app):
    """Serve NetraAttend at netra.PREFIX in front of OfficeEye's own pages."""
    if not _attendance_on():
        return

    def attendance_admin(environ):
        """Somebody already in OfficeEye is the attendance admin too - no second
        login. On the server: logged in to OfficeEye. On the office PC: logged in
        to OfficeEye (view or edit - the view login cannot change anything there,
        see guard below); with its login off, anybody on the office network
        (this PC or the network link), as OfficeEye itself, and a request from
        outside it still gets the attendance login."""
        if cloud.CLOUD:
            with app.request_context(environ):
                return cloud.signed_in()
        if access.enabled():
            with app.request_context(environ):
                return access.role() is not None
        return _office_network(environ.get("REMOTE_ADDR", ""))

    def guard(web):
        """The office PC's login in front of the attendance pages too: logged in
        first, and only the edit login changes anything (employees, entries,
        requests, its settings)."""
        def guarded(environ, start_response):
            if not cloud.CLOUD and access.enabled():
                with app.request_context(environ):
                    path = environ.get("SCRIPT_NAME", "") + environ.get("PATH_INFO", "")
                    why = access.check(environ, path)
                    if why:
                        qs = environ.get("QUERY_STRING", "")
                        res = app.make_response(access.refusal(why, environ, path + ("?" + qs if qs else "")))
                        return res(environ, start_response)
            return web(environ, start_response)
        return guarded

    try:
        import netra
        from werkzeug.middleware.dispatcher import DispatcherMiddleware
        web = netra.create_web_app(admin=attendance_admin)
    except Exception:                                    # noqa: BLE001 - OfficeEye runs on without it
        log.exception("attendance (NetraAttend) could not be added")
        return
    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {netra.PREFIX: guard(web)})
    app.jinja_env.globals.update(attendance_url="/attendance-app", attendance_nav=netra.NAV,
                                 attendance_prefix=netra.PREFIX)
    log.info("attendance (NetraAttend) at %s", netra.PREFIX)


@bp.get("/attendance-app")
def attendance_page():
    """NetraAttend's pages inside OfficeEye's window, under OfficeEye's sidebar
    (its Attendance menu). p: the attendance page, e.g. /employees."""
    globs = current_app.jinja_env.globals
    if "attendance_prefix" not in globs:
        abort(404)
    p = request.args.get("p", "/")
    if not p.startswith("/") or p.startswith("//"):
        p = "/"
    return page("attendance.html", "attendance", frame_src=globs["attendance_prefix"] + p)
