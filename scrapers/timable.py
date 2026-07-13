import json
import urllib.parse
from datetime import datetime, timedelta

from scrapers.common import http_get, make_id

SOURCE = "Timable"
# ponytail: 只爬首頁精選活動，唔夠全嘅話再加分類列表頁
PAGE_URL = "https://timable.com/hk/tc"
MARKER = "window.__remixContext = "


def _hk_date(iso):
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (dt + timedelta(hours=8)).date().isoformat()


def _walk(node, out):
    if isinstance(node, dict):
        if node.get("__typename") == "Event" and node.get("permalink"):
            out.append(node)
        for v in node.values():
            _walk(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk(v, out)


def fetch():
    html = http_get(PAGE_URL).text
    i = html.index(MARKER) + len(MARKER)
    ctx, _ = json.JSONDecoder().raw_decode(html[i:])
    found = []
    _walk(ctx, found)

    events = {}
    for ev in found:
        if not ev.get("name") or not ev.get("id"):
            continue
        dates, venue = [], ""
        for s in ev.get("sections") or []:
            for f in ("startDatetime", "endDatetime", "toThisDay"):
                if s.get(f):
                    dates.append(_hk_date(s[f]))
            if not venue:
                venue = ((s.get("location") or {}).get("name")
                         or s.get("address") or "")
        if not dates:
            continue
        eid = make_id(SOURCE, ev["id"])
        events[eid] = {
            "id": eid,
            "title": ev["name"],
            "category": "休閒",
            "start": min(dates),
            "end": max(dates),
            "venue": venue,
            "url": "https://timable.com/zh/event/"
                   + urllib.parse.quote(ev["permalink"]),
            "source": SOURCE,
        }
    return list(events.values())
