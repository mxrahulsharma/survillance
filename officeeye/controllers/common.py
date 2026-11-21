"""Small helpers the controllers share."""

import re
from datetime import datetime

from flask import abort, render_template, request

HM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")          # a time like 09:30


def page(template, name, **extra):
    """One of the app's pages (templates/), with the sidebar item `name` lit."""
    return render_template(template, page=name, **extra)


def day_arg():
    """?day=YYYY-MM-DD, today when it is not given; 400 when it is not a date."""
    day = (request.args.get("day") or "").strip()
    try:
        return datetime.strptime(day, "%Y-%m-%d").strftime("%Y-%m-%d") if day \
            else datetime.now().strftime("%Y-%m-%d")
    except ValueError:
        abort(400)
