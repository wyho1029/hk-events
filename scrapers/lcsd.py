import re
import xml.etree.ElementTree as ET

from scrapers.common import http_get, make_id

SOURCE = "康文署"
EVENTS_URL = "https://www.lcsd.gov.hk/datagovhk/event/events.xml"
VENUES_URL = "https://www.lcsd.gov.hk/datagovhk/event/venues.xml"
DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
FALLBACK_URL = "https://www.lcsd.gov.hk/tc/ticket/index.html"


def _venue_name(venues, venueid):
    # venueid（如 87310051）以 venues.xml 嘅 venue id 為前綴；揀最長匹配
    best = ""
    best_len = 0
    for vid, name in venues.items():
        if vid and venueid.startswith(vid) and len(vid) > best_len:
            best, best_len = name, len(vid)
    return best


def fetch():
    venues = {}
    for v in ET.fromstring(http_get(VENUES_URL).content).iter("venue"):
        venues[v.get("id") or ""] = (v.findtext("venuec") or "").strip()

    events = []
    for ev in ET.fromstring(http_get(EVENTS_URL).content).iter("event"):
        title = (ev.findtext("titlec") or "").strip()
        dates = [f"{y}-{m}-{d}" for d, m, y
                 in DATE_RE.findall(ev.findtext("predateC") or "")]
        if not title or not dates:
            continue
        events.append({
            "id": make_id(SOURCE, ev.get("id") or title),
            "title": title,
            "category": "休閒",
            "start": min(dates),
            "end": max(dates),
            "venue": _venue_name(venues,
                                 (ev.findtext("venueid") or "").strip()),
            "url": (ev.findtext("urlc") or "").strip() or FALLBACK_URL,
            "source": SOURCE,
        })
    return events
