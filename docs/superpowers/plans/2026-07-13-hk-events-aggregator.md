# 香港活動整合網站 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 自動整合香港即將舉行嘅體育／休閒／大型盛事活動，出一個 GitHub Pages 靜態網站，新活動推 Discord。

**Architecture:** Python 爬蟲（3 個已驗證來源）→ 合併去重過濾 → `docs/events.json` → 靜態 `docs/index.html` 顯示；GitHub Actions 每日 cron 跑，新活動經 webhook 推 Discord。

**Tech Stack:** Python 3.12、requests、beautifulsoup4、vanilla JS 一頁網站、GitHub Actions + Pages。

## Global Constraints

- 依賴只限 `requests`、`beautifulsoup4`（`pytest` 只限本地 dev，唔入 requirements.txt）。
- 所有 HTTP 經 `scrapers/common.py` 嘅 `http_get()`（瀏覽器 UA + 30s timeout）——直接 call `requests.get` 係錯。
- Event dict 統一 schema（欄位名一隻字都唔可以偏離）：
  `{"id": str, "title": str, "category": "體育"|"休閒"|"大型盛事", "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "venue": str, "url": str, "source": str}`
- 每個 fetcher 失敗只可以影響自己來源，唔可以令成個 job fail。
- Discord webhook 只可以經環境變數 `DISCORD_WEBHOOK_URL`／GitHub secret 攞，**永不寫入任何 commit 檔案**。
- 網站介面全繁體中文。
- 已驗證事實（2026-07-13 probe 結果，實施時直接用）：
  - LCSD `https://www.lcsd.gov.hk/datagovhk/event/events.xml` 同 `venues.xml`：可直接 GET，`<event id="...">` 內有 CDATA 欄位 `titlec`／`predateC`（格式如 `19/07/2026 (日) 20:00`）／`venueid`／`urlc`；venues.xml 係 `<venue id="875"><venuec>`，event 嘅 `venueid`（如 `87310051`）以 venue id 為前綴。
  - Timable `https://timable.com/hk/tc`：要瀏覽器 UA 先至 200；HTML 內嵌 `window.__remixContext = {...}`，入面有 `"__typename":"Event"` 物件（欄位：`id`、`permalink`、`name`、`sections[].startDatetime/endDatetime/toThisDay`（ISO UTC）、`sections[].location.name`、`sections[].address`）；活動頁 URL 格式 `https://timable.com/zh/event/{permalink}`（已驗證 200）。
  - Brand HK `https://www.brandhk.gov.hk/zh-hk/盛事之都/香港最新活動`：可直接 GET（帶 UA），server-rendered，每個活動係 `div.event-title` 內 `h2 a`（標題+外部連結）+ `p.content-txt` 文字 `活動日期: 2026年7月22日 - 2026年7月30日`。
  - URBTIX（JS SPA）、Cityline、KKTIX（403）：v1 唔做，README 記低係將來擴充。

---

### Task 1: 項目骨架 + 核心純函數

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `scrapers/__init__.py`（暫時空檔案）
- Create: `scrapers/common.py`
- Create: `scrape.py`
- Test: `tests/test_scrape.py`

**Interfaces:**
- Consumes: 冇（第一個 task）
- Produces:
  - `scrapers.common.http_get(url) -> requests.Response`（raise_for_status 咗）
  - `scrapers.common.make_id(source: str, key: str) -> str`（12 位 hex）
  - `scrape.is_entertainment(title: str) -> bool`
  - `scrape.categorize(title: str, default: str) -> str`
  - `scrape.valid(e: dict) -> bool`
  - `scrape.merge(lists: list[list[dict]], today: str) -> list[dict]`（去重＋過濾娛樂圈＋剔除已完結＋升級體育分類＋排序）
  - `scrape.find_new(events: list[dict], seen: dict[str, str]) -> list[dict]`

- [ ] **Step 1: 寫基礎檔案**

`requirements.txt`：
```
requests
beautifulsoup4
```

`.gitignore`：
```
__pycache__/
.pytest_cache/
```

`scrapers/common.py`：
```python
import hashlib

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def http_get(url):
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    return r


def make_id(source, key):
    return hashlib.sha1(f"{source}|{key}".encode("utf-8")).hexdigest()[:12]
```

- [ ] **Step 2: 寫 failing tests**

`tests/test_scrape.py`：
```python
import scrape


def make(id="a", title="活動", category="休閒", start="2099-01-01",
         end="2099-01-02"):
    return {"id": id, "title": title, "category": category, "start": start,
            "end": end, "venue": "", "url": "https://x", "source": "test"}


def test_is_entertainment():
    assert scrape.is_entertainment("巨星世界巡迴演唱會 2026")
    assert scrape.is_entertainment("XXX Fan Meeting in Hong Kong")
    assert not scrape.is_entertainment("香港馬拉松 2027")


def test_categorize():
    assert scrape.categorize("香港國際七人欖球賽", "大型盛事") == "體育"
    assert scrape.categorize("夏日手作市集", "休閒") == "休閒"


def test_valid():
    assert scrape.valid(make())
    assert not scrape.valid(make(start="2026/01/01"))
    assert not scrape.valid(make(category="娛樂"))
    bad = make()
    del bad["title"]
    assert not scrape.valid(bad)


def test_merge_dedupes_filters_and_sorts():
    a = make(id="1", start="2099-02-01", end="2099-02-01")
    dup = make(id="1", title="重複")
    ent = make(id="2", title="巨星演唱會")
    past = make(id="3", start="2000-01-01", end="2000-01-02")
    b = make(id="4", start="2099-01-01", end="2099-01-05")
    out = scrape.merge([[a, dup, ent], [past, b]], today="2026-07-13")
    assert [e["id"] for e in out] == ["4", "1"]


def test_merge_upgrades_sport_category():
    out = scrape.merge([[make(id="s", title="全港羽毛球錦標賽")]],
                       today="2026-07-13")
    assert out[0]["category"] == "體育"


def test_find_new():
    events = [make(id="1"), make(id="2")]
    assert [e["id"] for e in scrape.find_new(events, {"1": "2099-01-02"})] \
        == ["2"]
```

- [ ] **Step 3: 行 test 確認 fail**

Run: `python -m pytest tests/ -v`
Expected: FAIL（`scrape` module 未有啲 functions / import error）

- [ ] **Step 4: 寫 `scrape.py` 核心函數**

```python
import datetime

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
```

- [ ] **Step 5: 行 test 確認 pass**

Run: `python -m pytest tests/ -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .gitignore scrapers/ scrape.py tests/
git commit -m "feat: core event merge/filter logic"
```

---

### Task 2: 康文署 LCSD fetcher

**Files:**
- Create: `scrapers/lcsd.py`

**Interfaces:**
- Consumes: `scrapers.common.http_get`、`scrapers.common.make_id`
- Produces: `scrapers.lcsd.SOURCE = "康文署"`；`scrapers.lcsd.fetch() -> list[dict]`（Global Constraints 嘅 event schema）

- [ ] **Step 1: 寫 `scrapers/lcsd.py`**

```python
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
```

- [ ] **Step 2: Live check（爬蟲唔寫 fixture test，用真數據 smoke check）**

Run:
```bash
python -c "from scrapers import lcsd; evs = lcsd.fetch(); print(len(evs)); [print(e) for e in evs[:3]]"
```
Expected: 印出活動數量（通常過百）同 3 個完整 event dict；`start`/`end` 係 `YYYY-MM-DD`；大部分 event 嘅 `venue` 唔係空字串。如果 `venue` 大面積係空，檢查 `_venue_name` 前綴邏輯（印幾個 `venueid` 同 venues.xml 嘅 id 對比）。

- [ ] **Step 3: Commit**

```bash
git add scrapers/lcsd.py
git commit -m "feat: LCSD events fetcher"
```

---

### Task 3: Timable fetcher

**Files:**
- Create: `scrapers/timable.py`

**Interfaces:**
- Consumes: `scrapers.common.http_get`、`scrapers.common.make_id`
- Produces: `scrapers.timable.SOURCE = "Timable"`；`scrapers.timable.fetch() -> list[dict]`

- [ ] **Step 1: 寫 `scrapers/timable.py`**

```python
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
```

- [ ] **Step 2: Live check**

Run:
```bash
python -c "from scrapers import timable; evs = timable.fetch(); print(len(evs)); [print(e) for e in evs[:3]]"
```
Expected: 活動數量 > 0（首頁通常有幾十個）；抽一個 `url` 喺瀏覽器開，確認去到正確活動頁。如果 `html.index(MARKER)` raise ValueError，將頁面 HTML 存檔 grep `__remixContext` 睇實際 marker 寫法再調整 `MARKER`。

- [ ] **Step 3: Commit**

```bash
git add scrapers/timable.py
git commit -m "feat: Timable fetcher via embedded remix context"
```

---

### Task 4: Brand HK 盛事 fetcher

**Files:**
- Create: `scrapers/brandhk.py`

**Interfaces:**
- Consumes: `scrapers.common.http_get`、`scrapers.common.make_id`
- Produces: `scrapers.brandhk.SOURCE = "盛事之都"`；`scrapers.brandhk.fetch() -> list[dict]`

- [ ] **Step 1: 寫 `scrapers/brandhk.py`**

```python
import re

from bs4 import BeautifulSoup

from scrapers.common import http_get, make_id

SOURCE = "盛事之都"
PAGE_URL = "https://www.brandhk.gov.hk/zh-hk/盛事之都/香港最新活動"
DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")


def fetch():
    soup = BeautifulSoup(http_get(PAGE_URL).text, "html.parser")
    events = []
    for block in soup.select("div.event-title"):
        a = block.select_one("h2 a")
        if a is None:
            continue
        title = a.get_text(strip=True)
        text = block.get_text(" ", strip=True)
        dates = [f"{y}-{int(m):02d}-{int(d):02d}"
                 for y, m, d in DATE_RE.findall(text)]
        if not title or not dates:
            continue
        m = re.search(r"(?:地點|地址)[:：]\s*(\S+)", text)
        events.append({
            "id": make_id(SOURCE, title + dates[0]),
            "title": title,
            "category": "大型盛事",
            "start": min(dates),
            "end": max(dates),
            "venue": m.group(1) if m else "",
            "url": a.get("href") or PAGE_URL,
            "source": SOURCE,
        })
    return events
```

- [ ] **Step 2: Live check**

Run:
```bash
python -c "from scrapers import brandhk; evs = brandhk.fetch(); print(len(evs)); [print(e) for e in evs[:5]]"
```
Expected: 活動數量 > 0；標題係「世界劍擊錦標賽2026中國香港」呢類盛事；日期正確。如果 0 個，將 HTML 存檔檢查 `div.event-title` selector 有冇改。

- [ ] **Step 3: Commit**

```bash
git add scrapers/brandhk.py
git commit -m "feat: Brand HK mega events fetcher"
```

---

### Task 5: 組裝 orchestrator（main → events.json）

**Files:**
- Modify: `scrapers/__init__.py`
- Modify: `scrape.py`（加 `previous_events`、`main`；Task 1 嘅函數唔郁）

**Interfaces:**
- Consumes: 三個 fetcher module（`SOURCE`、`fetch`）；Task 1 嘅 `merge`
- Produces:
  - `scrapers.FETCHERS: list[tuple[str, callable]]`
  - `scrape.previous_events(source: str) -> list[dict]`
  - `scrape.main()`；產出 `docs/events.json`，格式 `{"updated": "YYYY-MM-DD", "events": [...]}`

- [ ] **Step 1: 寫 `scrapers/__init__.py`**

```python
from scrapers import brandhk, lcsd, timable

FETCHERS = [
    (lcsd.SOURCE, lcsd.fetch),
    (timable.SOURCE, timable.fetch),
    (brandhk.SOURCE, brandhk.fetch),
]
```

- [ ] **Step 2: 喺 `scrape.py` 加 orchestrator**

檔案頂部加 import（保留原有內容）：
```python
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVENTS_PATH = ROOT / "docs" / "events.json"
```

檔案尾部加：
```python
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
```

- [ ] **Step 3: 行 tests 確認冇整爛嘢**

Run: `python -m pytest tests/ -v`
Expected: 全部 PASS

- [ ] **Step 4: Live check 全流程**

Run: `python scrape.py`
Expected: 三行 `來源: N events`、一行 `total: ...`；`docs/events.json` 生成，開嚟肉眼睇：冇演唱會、日期全部 >= 今日、三個 source 都有出現。

- [ ] **Step 5: Commit**

```bash
git add scrapers/__init__.py scrape.py docs/events.json
git commit -m "feat: orchestrator writes docs/events.json"
```

---

### Task 6: Discord 推送 + seen state

**Files:**
- Modify: `scrape.py`
- Test: `tests/test_scrape.py`（加 test）

**Interfaces:**
- Consumes: Task 1 嘅 `find_new`；Task 5 嘅 `main`
- Produces:
  - `scrape.build_discord_payload(new_events: list[dict]) -> dict`（Discord webhook JSON）
  - `scrape.push_discord(webhook: str, new_events: list[dict])`
  - `main()` 加入：讀寫 `state/seen.json`（`{event_id: end_date}`）；首次行（冇 seen.json）只 seed 唔推送；推送失敗唔 fail job；seen 剪走完結超過 30 日嘅 id

- [ ] **Step 1: 加 failing test**

Append 落 `tests/test_scrape.py`：
```python
def test_discord_payload_caps_at_20():
    events = [make(id=str(i), title=f"活動{i}") for i in range(25)]
    p = scrape.build_discord_payload(events)
    desc = p["embeds"][0]["description"]
    assert "25" in p["embeds"][0]["title"]
    assert "仲有 5 個" in desc
    assert len(desc) <= 4096
```

- [ ] **Step 2: 行 test 確認 fail**

Run: `python -m pytest tests/ -v -k discord`
Expected: FAIL（`build_discord_payload` 未定義）

- [ ] **Step 3: 實作**

`scrape.py` 加：
```python
import os

import requests

SEEN_PATH = ROOT / "state" / "seen.json"


def build_discord_payload(new_events):
    lines = [f'{e["start"]}｜[{e["title"]}]({e["url"]})'
             f'｜{e["category"]}{"｜" + e["venue"] if e["venue"] else ""}'
             for e in new_events[:20]]
    if len(new_events) > 20:
        lines.append(f"……仲有 {len(new_events) - 20} 個新活動，上網站睇晒")
    return {"embeds": [{
        "title": f"🆕 香港新活動（{len(new_events)} 個）",
        "description": "\n".join(lines)[:4096],
        "color": 0x00B894,
    }]}


def push_discord(webhook, new_events):
    r = requests.post(webhook, json=build_discord_payload(new_events),
                      timeout=30)
    r.raise_for_status()
```

`main()` 裡面，`print(f"total: ...")` 之後加：
```python
    first_run = not SEEN_PATH.exists()
    seen = {} if first_run \
        else json.loads(SEEN_PATH.read_text(encoding="utf-8"))
    new = find_new(events, seen)
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if new and webhook and not first_run:
        try:
            push_discord(webhook, new)
            print(f"discord: pushed {len(new)} new events")
        except Exception:
            print("discord: push failed")
            traceback.print_exc()

    for e in events:
        seen[e["id"]] = e["end"]
    cutoff = (datetime.date.today()
              - datetime.timedelta(days=30)).isoformat()
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    SEEN_PATH.parent.mkdir(exist_ok=True)
    SEEN_PATH.write_text(json.dumps(seen, ensure_ascii=False),
                         encoding="utf-8")
```

- [ ] **Step 4: 行 test 確認 pass**

Run: `python -m pytest tests/ -v`
Expected: 全部 PASS

- [ ] **Step 5: Live check（用真 webhook）**

PowerShell（webhook 值問用戶攞，唔好 hardcode 落任何檔案）：
```powershell
$env:DISCORD_WEBHOOK_URL = "<用戶提供嘅 webhook>"
python scrape.py   # 第一次：seed，唔應該推
python -c "import json,pathlib; p=pathlib.Path('state/seen.json'); d=json.loads(p.read_text(encoding='utf-8')); k=next(iter(d)); del d[k]; p.write_text(json.dumps(d), encoding='utf-8')"
python scrape.py   # 第二次：應該推 1 個「新」活動去 Discord
```
Expected: 第一次 output 冇 `discord:` 行；第二次有 `discord: pushed 1 new events`，Discord channel 收到一條 embed。

- [ ] **Step 6: Commit**

```bash
git add scrape.py tests/test_scrape.py state/seen.json
git commit -m "feat: discord push for newly discovered events"
```

---

### Task 7: 網站 `docs/index.html`

**Files:**
- Create: `docs/index.html`

**Interfaces:**
- Consumes: `docs/events.json`（`{"updated", "events": [...]}`，event schema 見 Global Constraints）
- Produces: GitHub Pages 直接 serve 嘅一頁式網站

- [ ] **Step 1: 寫 `docs/index.html`**

完整內容（vanilla JS，冇 build step；實施時可以用 frontend-design skill 執靚 CSS，但功能結構照以下寫）：

```html
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>香港活動一覽</title>
<style>
  :root { --bg:#fff; --fg:#1a1a1a; --muted:#666; --card:#f5f5f5;
          --accent:#00795c; --chip:#e5e5e5; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#111; --fg:#eee; --muted:#999; --card:#1d1d1d;
            --chip:#333; --accent:#2bbf96; }
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font-family:system-ui, "Microsoft JhengHei", sans-serif; }
  header { position:sticky; top:0; background:var(--bg); padding:12px 16px;
           border-bottom:1px solid var(--chip); }
  h1 { font-size:20px; margin:0 0 8px; }
  #updated { color:var(--muted); font-size:12px; }
  .controls { display:flex; gap:8px; flex-wrap:wrap; margin-top:8px; }
  .controls button { border:none; background:var(--chip); color:var(--fg);
                     padding:6px 14px; border-radius:16px; cursor:pointer; }
  .controls button.on { background:var(--accent); color:#fff; }
  #q { flex:1; min-width:140px; padding:6px 12px; border-radius:16px;
       border:1px solid var(--chip); background:var(--bg); color:var(--fg); }
  main { max-width:720px; margin:0 auto; padding:16px; }
  .ev { background:var(--card); border-radius:10px; padding:12px 14px;
        margin-bottom:10px; }
  .ev a { color:var(--fg); text-decoration:none; font-weight:600; }
  .ev a:hover { color:var(--accent); }
  .meta { color:var(--muted); font-size:13px; margin-top:4px; }
  .tag { display:inline-block; font-size:12px; padding:1px 8px;
         border-radius:10px; background:var(--accent); color:#fff;
         margin-right:6px; }
  #empty { color:var(--muted); text-align:center; padding:40px 0; }
</style>
</head>
<body>
<header>
  <h1>香港活動一覽 <span id="updated"></span></h1>
  <div class="controls" id="cats">
    <button data-c="" class="on">全部</button>
    <button data-c="體育">體育</button>
    <button data-c="休閒">休閒</button>
    <button data-c="大型盛事">大型盛事</button>
    <input id="q" type="search" placeholder="搜尋活動／場地…">
  </div>
</header>
<main><div id="list"></div><div id="empty" hidden>冇符合嘅活動</div></main>
<script>
let EVENTS = [], cat = "", q = "";

function fmt(e) {
  return e.start === e.end ? e.start : e.start + " 至 " + e.end;
}

function render() {
  const kw = q.trim().toLowerCase();
  const hits = EVENTS.filter(e =>
    (!cat || e.category === cat) &&
    (!kw || (e.title + e.venue).toLowerCase().includes(kw)));
  document.getElementById("list").innerHTML = hits.map(e => `
    <div class="ev">
      <a href="${e.url}" target="_blank" rel="noopener">${e.title}</a>
      <div class="meta"><span class="tag">${e.category}</span>
        ${fmt(e)}${e.venue ? "｜" + e.venue : ""}｜來源：${e.source}</div>
    </div>`).join("");
  document.getElementById("empty").hidden = hits.length > 0;
}

document.getElementById("cats").addEventListener("click", ev => {
  if (ev.target.tagName !== "BUTTON") return;
  document.querySelectorAll("#cats button")
    .forEach(b => b.classList.toggle("on", b === ev.target));
  cat = ev.target.dataset.c;
  render();
});
document.getElementById("q").addEventListener("input", ev => {
  q = ev.target.value;
  render();
});

fetch("events.json").then(r => r.json()).then(d => {
  EVENTS = d.events;
  document.getElementById("updated").textContent = "（更新於 " + d.updated + "）";
  render();
});
</script>
</body>
</html>
```

- [ ] **Step 2: 本地 verify**

Run: `python -m http.server 8000 --directory docs`（背景行），瀏覽器開 `http://localhost:8000`。
Expected: 活動列表顯示、分類掣切換正常、搜尋即時過濾、手機闊度（DevTools responsive）冇爆版。搞掂後停個 server。

- [ ] **Step 3: Commit**

```bash
git add docs/index.html
git commit -m "feat: static events site"
```

---

### Task 8: GitHub Actions workflow + README

**Files:**
- Create: `.github/workflows/update.yml`
- Create: `README.md`

**Interfaces:**
- Consumes: `scrape.py main()`；repo secret `DISCORD_WEBHOOK_URL`
- Produces: 每日 01:00 UTC（09:00 HKT）自動更新 + 可手動觸發

- [ ] **Step 1: 寫 `.github/workflows/update.yml`**

```yaml
name: update-events
on:
  schedule:
    - cron: "0 1 * * *"   # 09:00 HKT
  workflow_dispatch:
permissions:
  contents: write
jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python scrape.py
        env:
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
      - name: commit and push if changed
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add docs/events.json state/seen.json
          git diff --cached --quiet || git commit -m "chore: update events $(date -u +%F)"
          git push
```

- [ ] **Step 2: 寫 `README.md`**

```markdown
# 香港活動一覽

自動整合香港即將舉行嘅體育／休閒／大型盛事活動（唔收錄娛樂圈活動），
每日 09:00 HKT 更新，新活動推送 Discord。

## 資料來源

- 康文署（data.gov.hk 官方 XML）
- Timable
- Brand HK 盛事之都

將來想加：URBTIX／Cityline／KKTIX（而家有反爬蟲，暫時冇做）。

## 點運作

GitHub Actions 每日跑 `python scrape.py`：爬料 → 過濾娛樂圈活動 →
出 `docs/events.json` → GitHub Pages 顯示 → 新活動經 webhook 推 Discord。

## 本地行

    pip install -r requirements.txt
    python scrape.py          # 唔設 DISCORD_WEBHOOK_URL 就唔會推送
    python -m pytest tests/   # 行測試

## 設定

- Repo secret `DISCORD_WEBHOOK_URL`：Discord webhook。
- GitHub Pages：Settings → Pages → Deploy from branch → `master` / `docs`。
```

- [ ] **Step 3: Commit**

```bash
git add .github/ README.md
git commit -m "feat: daily github actions workflow + readme"
```

---

### Task 9: 部署去 GitHub + 端到端驗證

**Files:** 冇新檔案（部署操作）

**Interfaces:**
- Consumes: 成個 repo；用戶嘅 GitHub 帳號（`gh auth login` 如未登入）；webhook secret
- Produces: 上線嘅網站 URL + 運作中嘅每日自動更新

- [ ] **Step 1: 確認 gh CLI 登入咗**

Run: `gh auth status`
Expected: 顯示已登入帳號。未登入就叫用戶行 `gh auth login`（互動式，要用戶親自做）。

- [ ] **Step 2: 開 repo 並 push**

```bash
gh repo create hk-events --public --source . --push
```
Expected: repo 建立，master push 咗上去。

- [ ] **Step 3: 設 secret（webhook 值問用戶攞，唔好寫落檔案）**

```bash
gh secret set DISCORD_WEBHOOK_URL
```
（互動輸入 webhook 值，或者 `--body` 由環境變數帶入。）

- [ ] **Step 4: 開 GitHub Pages**

```bash
gh api -X POST "repos/{owner}/hk-events/pages" -f "source[branch]=master" -f "source[path]=/docs"
```
Expected: 201。如果已存在會 409，可以無視。

- [ ] **Step 5: 手動觸發 workflow 驗證**

```bash
gh workflow run update-events
gh run watch
```
Expected: run 成功；repo 有新 commit（如資料有變）；因為 seen.json 已經 seed 咗，Discord 唔應該收到 spam。

- [ ] **Step 6: 驗證網站上線**

Run: `gh api "repos/{owner}/hk-events/pages" --jq .html_url`
瀏覽器開返嚟嘅 URL。
Expected: 網站正常顯示活動。將 URL 話俾用戶知。

- [ ] **Step 7: 完成**

向用戶匯報：網站 URL、Discord 推送機制（每日 09:00 HKT，有新活動先推）、點樣手動觸發（Actions → update-events → Run workflow）。
