"""Running time: how many hours each camera was connected, per period and
day by day, with CSV downloads."""

from datetime import datetime, timedelta

from flask import Blueprint, Response, jsonify, redirect, request

from officeeye.controllers.common import day_arg, page
from officeeye.models import events
from officeeye.services.sources import manager

bp = Blueprint("running_time", __name__)


@bp.get("/running-time")
def running_time_page():
    return page("running_time.html", "running")


@bp.get("/uptime")
def uptime_page():
    return redirect("/running-time")


def _uptime_report():
    day = day_arg()
    days = min(max(int(request.args.get("days", 1)), 1), 90)
    data = events.uptime(day, days)
    start = datetime.strptime(data["first"], "%Y-%m-%d")
    end = min(datetime.strptime(day, "%Y-%m-%d") + timedelta(days=1), datetime.now())
    cams = []
    for cam_id, st in manager.status().items():
        u = data["cameras"].get(cam_id, {})
        cams.append({"id": cam_id, "name": st["name"], "group": st["group"],
                     "ip": st["ip"], "state": st.get("state"),
                     "online": round(u.get("online", 0)),
                     "offline": round(u.get("offline", 0)),
                     "drops": u.get("drops", 0),
                     "last_online": u.get("last_online"),
                     "hours": u.get("hours", {})})
    return {"first": data["first"], "last": day, "days": days,
            "period": max(0, round((end - start).total_seconds())), "cameras": cams}


@bp.get("/api/running-time")
def api_running_time():
    """How many hours each camera was connected and how many it was off."""
    return jsonify(_uptime_report())


@bp.get("/api/running-time.csv")
def api_running_time_csv():
    r = _uptime_report()
    hours = lambda s: f"{s / 3600:.2f}"
    lines = ["camera,name,purpose,ip,online_hours,offline_hours,app_not_running_hours,"
             "running_percent,drops,last_online,from,to"]
    for c in r["cameras"]:
        seen = c["online"] + c["offline"]
        cells = [c["id"], c["name"], c["group"], c["ip"], hours(c["online"]),
                 hours(c["offline"]), hours(max(0, r["period"] - seen)),
                 f"{100 * c['online'] / seen:.1f}" if seen else "",
                 str(c["drops"]), c["last_online"] or "", r["first"], r["last"]]
        lines.append(",".join('"' + str(v).replace('"', '""') + '"' for v in cells))
    name = f"camera-running-time-{r['first']}" + ("" if r["days"] == 1 else f"-to-{r['last']}")
    return Response("\r\n".join(lines) + "\r\n", mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})


def _daily_rows():
    """Saved daily records (per camera per day) for the last `days` days,
    plus today so far, newest first. ?camera= keeps one camera."""
    days = min(max(int(request.args.get("days", 30)), 1), 3660)
    camera = request.args.get("camera") or None
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    first = (now - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    names = {k: v["name"] for k, v in manager.status().items()}
    live = events.uptime(today)["cameras"]
    since_midnight = (now - now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
    rows = []
    for cam_id, u in live.items():
        if camera and cam_id != camera:
            continue
        rows.append({"day": today, "today": True, "camera": cam_id,
                     "name": names.get(cam_id, cam_id),
                     "running": round(u["online"]), "off": round(u["offline"]),
                     "not_watched": max(0, round(since_midnight - u["online"] - u["offline"])),
                     "drops": u["drops"], "last_online": u["last_online"]})
    rows.sort(key=lambda r: r["camera"])
    rows += events.camera_days(first, today, camera)
    return first, today, camera, rows


@bp.get("/api/running-time/days")
def api_running_days():
    """The day-by-day record: per camera, or every camera added up."""
    first, last, camera, rows = _daily_rows()
    if camera:
        return jsonify({"first": first, "last": last, "camera": camera, "rows": rows})
    days = {}
    for r in rows:
        d = days.setdefault(r["day"], {"day": r["day"], "today": r.get("today", False),
                                       "cameras": 0, "running": 0, "off": 0, "drops": 0,
                                       "worst": None})
        d["cameras"] += 1
        d["running"] += r["running"]
        d["off"] += r["off"]
        d["drops"] += r["drops"]
        if r["off"] >= 60 and (d["worst"] is None or r["off"] > d["worst"]["off"]):
            d["worst"] = {"name": r["name"], "off": r["off"]}
    return jsonify({"first": first, "last": last, "camera": None,
                    "rows": sorted(days.values(), key=lambda d: d["day"], reverse=True)})


@bp.get("/api/running-time/days.csv")
def api_running_days_csv():
    first, last, camera, rows = _daily_rows()
    hours = lambda s: f"{s / 3600:.2f}"
    lines = ["day,camera,name,running_hours,off_hours,app_not_running_hours,"
             "running_percent,drops,last_online,complete_day"]
    for r in rows:
        seen = r["running"] + r["off"]
        cells = [r["day"], r["camera"], r["name"], hours(r["running"]), hours(r["off"]),
                 hours(r["not_watched"]), f"{100 * r['running'] / seen:.1f}" if seen else "",
                 r["drops"], r["last_online"] or "", "no - today so far" if r.get("today") else "yes"]
        lines.append(",".join('"' + str(v).replace('"', '""') + '"' for v in cells))
    name = f"camera-daily-running-time-{first}-to-{last}" + (f"-{camera}" if camera else "")
    return Response("\r\n".join(lines) + "\r\n", mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})
