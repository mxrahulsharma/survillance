"""The live status every page polls (/api/status): cameras, counts, alerts.
The office PC also sends it to the cloud view (core/cloud.py)."""

from datetime import datetime

from officeeye.models import events
from officeeye.services import fire, health
from officeeye.services.sources import manager, pipeline

NOTICE_KINDS = ("parking", health.KIND, fire.KIND)      # shown as a note on every page


def status_payload():
    cams = manager.status()
    live = pipeline.live()
    peaks = events.peak("person_count")
    total = on_phone = 0
    reporting = 0
    alerting = []
    for cam_id, st in cams.items():
        st.update(live.get(cam_id, {}))
        st["peak"] = peaks.get(cam_id)
        if st.get("count") is not None:
            total += st["count"]
            reporting += 1
        on_phone += st.get("on_phone") or 0
        if (st.get("alert") or {}).get("active"):
            alerting.append(cam_id)
    return {
        "cameras": cams,
        "detection": pipeline.status(),
        "total": total,
        "reporting": reporting,
        "on_phone_total": on_phone,
        "peak_today": max(peaks.values()) if peaks else None,
        "alerting": alerting,
        "latest_alert": events.latest_id("restricted_alert"),
        "latest_notice": events.latest_of(NOTICE_KINDS),
        "health_problems": health.monitor.problems(),
        "fire_now": fire.watch.open_count(),
        "alerts_today": events.count_today("restricted_alert"),
        "phone_today": events.count_today("phone_use", with_photos=True),
        "server_time": datetime.now().isoformat(timespec="seconds"),
    }
