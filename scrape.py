import datetime
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVENTS_PATH = ROOT / "docs" / "events.json"

CATEGORIES = {"體育", "休閒", "大型盛事"}

# 過濾娛樂圈活動嘅關鍵字，逐個小寫 substring 匹配，隨時加減
EXCLUDE_KEYWORDS = ["演唱會", "見面會", "歌迷", "粉絲", "簽唱", "簽售",
                    "應援", "fan meeting", "fans meeting", "fanmeeting"]

SPORT_KEYWORDS = ["馬拉松", "跑", "欖球", "足球", "籃球", "排球", "網球",
                  "羽毛球", "乒乓球", "游泳", "單車", "劍擊", "體育", "運動",
                  "錦標賽", "格蘭披治", "賽馬", "龍舟", "帆船", "高爾夫",
                  "武術", "拳"]


def is_entertainment(title):
    t = title.lower()
    return any(k in t for k in EXCLUDE_KEYWORDS)


def categorize(title, default):
    if any(k in title for k in SPORT_KEYWORDS):
        return "體育"
    return default


def valid(e):
    try:
        datetime.date.fromisoformat(e["start"])
        datetime.date.fromisoformat(e["end"])
        return bool(e["id"] and e["title"] and e["url"] and e["source"]) \
            and e["category"] in CATEGORIES
    except (KeyError, TypeError, ValueError):
        return False


def merge(lists, today):
    out = {}
    for events in lists:
        for e in events:
            if not valid(e) or is_entertainment(e["title"]) \
                    or e["end"] < today:
                continue
            e = dict(e, category=categorize(e["title"], e["category"]))
            out.setdefault(e["id"], e)
    return sorted(out.values(), key=lambda e: (e["start"], e["title"]))


def find_new(events, seen):
    return [e for e in events if e["id"] not in seen]


def previous_events(source):
    """一個來源今次 fail，用返佢上次成功嘅資料。"""
    try:
        data = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
        return [e for e in data["events"] if e["source"] == source]
    except (OSError, ValueError, KeyError):
        return []


def main():
    from scrapers import FETCHERS
    today = datetime.date.today().isoformat()
    results, ok = [], 0
    for name, fetch in FETCHERS:
        try:
            events = fetch()
            ok += 1
            print(f"{name}: {len(events)} events")
        except Exception:
            print(f"{name}: FAILED, using previous data")
            traceback.print_exc()
            events = previous_events(name)
        results.append(events)
    if ok == 0:
        sys.exit("all fetchers failed")

    events = merge(results, today)
    EVENTS_PATH.parent.mkdir(exist_ok=True)
    EVENTS_PATH.write_text(
        json.dumps({"updated": today, "events": events},
                   ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"total: {len(events)} events -> {EVENTS_PATH}")


if __name__ == "__main__":
    main()
