import datetime
import json
import os
import re
import sys
import traceback
import urllib.parse
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
EVENTS_PATH = ROOT / "docs" / "events.json"
SEEN_PATH = ROOT / "state" / "seen.json"

CATEGORIES = {"體育", "休閒", "大型盛事", "表演藝術", "展覽",
              "電影", "電影活動", "親子", "市集", "演唱會"}

# 過濾娛樂圈活動嘅關鍵字，逐個小寫 substring 匹配，隨時加減
# （演唱會有自己嘅分類，唔再過濾；見面會／簽唱等粉絲活動照隔走）
EXCLUDE_KEYWORDS = ["見面會", "歌迷", "粉絲", "簽唱", "簽售",
                    "應援", "fan meeting", "fans meeting", "fanmeeting"]

# 用具體字眼，避免單字誤判（「跑」中「跑道」展覽、「拳」中無關詞）
SPORT_KEYWORDS = ["馬拉松", "跑步", "賽跑", "路跑", "越野跑", "接力賽",
                  "欖球", "足球", "籃球", "排球", "網球",
                  "羽毛球", "乒乓球", "游泳", "單車", "劍擊", "體育", "運動",
                  "錦標賽", "格蘭披治", "賽馬", "龍舟", "帆船", "高爾夫",
                  "武術", "拳擊", "泰拳"]

# 按優先次序逐組匹配標題，第一組中就係嗰類；全部唔中先用來源預設
CATEGORY_KEYWORDS = [
    ("體育", SPORT_KEYWORDS),
    ("電影活動", ["電影", "放映", "影展"]),
    ("市集", ["市集", "墟", "夜市"]),
    ("展覽", ["展覽", "特展", "博覽", "大展", "藝術展", "常設展",
              "畫展", "攝影展", "聯展", "個展", "展出", "巡迴展",
              "書展"]),
    # 粵曲演唱會呢類傳統曲藝要贏「演唱會」keyword，所以排先
    ("表演藝術", ["粵曲", "粵劇", "折子戲", "戲曲", "粵韻"]),
    ("演唱會", ["演唱會", "拉闊", "巡唱", "巡迴演唱",
                  "world tour", "live in hong kong", "live in hk"]),
    ("表演藝術", ["音樂會", "演奏", "管弦", "交響", "合唱", "爵士", "室樂",
                  "音樂節", "戲劇", "話劇", "舞蹈", "舞劇",
                  "歌劇", "音樂劇", "劇場", "木偶", "演藝",
                  "金曲", "知音", "匯演", "雜技", "樂韻",
                  "獨奏", "重奏", "演唱", "朗誦", "歌舞",
                  "管樂", "弦樂", "中樂", "笛", "琴"]),
    ("親子", ["親子", "兒童", "合家歡", "小朋友"]),
]


def is_entertainment(title):
    t = title.lower()
    return any(k in t for k in EXCLUDE_KEYWORDS)


def categorize(title, default):
    t = title.lower()  # 小寫比對，令英文 keyword（world tour 等）唔分大小寫
    for cat, keywords in CATEGORY_KEYWORDS:
        if any(k.lower() in t for k in keywords):
            return cat
    return default


def _url_ok(url):
    """host 要有點、冇空白／括號，擋 https://cpuac2010(instagram) 呢類壞 URL。"""
    u = url if "://" in url else "https://" + url
    host = urllib.parse.urlparse(u).netloc.split("@")[-1].split(":")[0]
    return bool("." in host and not re.search(r"[\s()]", host))


def valid(e):
    try:
        datetime.date.fromisoformat(e["start"])
        datetime.date.fromisoformat(e["end"])
    except (KeyError, TypeError, ValueError):
        return False
    return bool(e.get("id") and e.get("title")
                and e.get("url") and e.get("source")) \
        and e.get("category") in CATEGORIES \
        and e["start"] <= e["end"] \
        and _url_ok(e["url"])


def merge(lists, today):
    out = {}
    for events in lists:
        for e in events:
            if not valid(e) or is_entertainment(e["title"]) \
                    or e["end"] < today:
                continue
            # 院線電影（爬蟲已標 category=電影）保留原分類，唔行 categorize
            cat = e["category"] if e["category"] == "電影" \
                else categorize(e["title"], e["category"])
            e = dict(e, title=" ".join(e["title"].split()),
                     category=cat,
                     image=e.get("image", ""))
            if not e["url"].startswith("http"):
                e["url"] = "https://" + e["url"]
            e["featured"] = is_featured(e)
            out.setdefault(e["id"], e)
    return sorted(out.values(), key=lambda e: (e["start"], e["title"]))


# 世界級／大型體育賽事嘅字眼，用嚟將體育盛事升做「精選」
MAJOR_SPORT_KEYWORDS = ["世界", "國際", "錦標賽", "公開賽", "大師賽",
                        "格蘭披治", "馬拉松", "欖球", "sevens"]


def is_featured(e):
    """必睇盛事：大型盛事，或世界級體育賽事。"""
    if e["category"] == "大型盛事":
        return True
    if e["category"] == "體育":
        t = e["title"].lower()
        return any(k in t for k in MAJOR_SPORT_KEYWORDS)
    return False


def find_new(events, seen):
    return [e for e in events if e["id"] not in seen]


def discord_events(new_events):
    """院線電影同演唱會只喺網站顯示，唔推 Discord
    （電影每日換片會洗版；演唱會多為娛樂性質，用戶唔想收推送）。"""
    return [e for e in new_events
            if e["category"] not in ("電影", "演唱會")]


def build_discord_payload(new_events):
    lines = []
    total = 0
    shown = 0
    for e in new_events[:20]:
        title = e["title"].replace("[", "\\[").replace("]", "\\]")
        line = (f'{e["start"]}｜[{title}]({e["url"]})'
                f'｜{e["category"]}{"｜" + e["venue"] if e["venue"] else ""}')
        added = len(line) if not lines else len(line) + 1
        if total + added > 4000:
            break
        lines.append(line)
        total += added
        shown += 1
    remaining = len(new_events) - shown
    if remaining > 0:
        lines.append(f"……仲有 {remaining} 個新活動，上網站睇晒")
    return {"embeds": [{
        "title": f"🆕 香港新活動（{len(new_events)} 個）",
        "description": "\n".join(lines),
        "color": 0x00B894,
    }]}


def push_discord(webhook, new_events):
    r = requests.post(webhook, json=build_discord_payload(new_events),
                      timeout=30)
    r.raise_for_status()


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
            if not events:
                # 空結果（例：WAF 回 200 challenge、selector 失效）當失敗，
                # 唔好用空清單覆寫，改用上次成功資料，否則會刪走成個來源
                raise ValueError("empty result")
            ok += 1
            print(f"{name}: {len(events)} events")
        except Exception:
            print(f"{name}: FAILED/empty, using previous data")
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

    first_run = not SEEN_PATH.exists()
    seen = {} if first_run \
        else json.loads(SEEN_PATH.read_text(encoding="utf-8"))
    new = find_new(events, seen)
    to_push = discord_events(new)
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
    retry_ids = set()
    if to_push and webhook and not first_run:
        try:
            push_discord(webhook, to_push)
            print(f"discord: pushed {len(to_push)} new events")
        except Exception:
            retry_ids = {e["id"] for e in to_push}
            print("discord: push failed, will retry next run")
            traceback.print_exc()

    for e in events:
        if e["id"] not in retry_ids:
            seen[e["id"]] = e["end"]
    cutoff = (datetime.date.today()
              - datetime.timedelta(days=30)).isoformat()
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    SEEN_PATH.parent.mkdir(exist_ok=True)
    SEEN_PATH.write_text(json.dumps(seen, ensure_ascii=False),
                         encoding="utf-8")


if __name__ == "__main__":
    main()
