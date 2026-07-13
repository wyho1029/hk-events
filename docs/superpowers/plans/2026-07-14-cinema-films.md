# 戲院上畫電影分類 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 現有「電影」分類改名做「電影活動」，新增真正「電影」分類收錄 hkmovie6 院線上映電影；院線電影唔推 Discord。

**Architecture:** 沿用現有管線（scrapers → merge → events.json → 靜態站 → Discord），加一個 hkmovie6 爬蟲 + 少量 wiring + 前端 chip。

**Tech Stack:** Python 3.12、requests、beautifulsoup4、vanilla JS、GitHub Actions + Pages。

## Global Constraints

- 依賴只限 `requests`、`beautifulsoup4`（pytest 只限本地 dev，唔入 requirements.txt）。
- 所有 HTTP 經 `scrapers/common.py` 嘅 `http_get()`（瀏覽器 UA + 30s timeout）。
- Event dict 統一 schema（欄位名一隻字都唔可以偏離）：
  `{"id": str, "title": str, "category": str, "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "venue": str, "url": str, "source": str, "image": str, "featured": bool}`
  （`image`／`featured` 由 `merge()` 補齊，爬蟲層可只提供 `image`。）
- `CATEGORIES` 合法值（本計劃後）：體育、休閒、大型盛事、表演藝術、展覽、電影、電影活動、親子。
- 每個 fetcher 失敗只可以影響自己來源，唔可以令成個 job fail。
- 院線電影（`source == "hkmovie6"`）喺 `merge()` 保留 `category == "電影"`，唔行 `categorize()`（避免戲名含 keyword 時被降級）。
- Discord 推送前隔走 `category == "電影"`；seen 照記所有 events（院線電影永不經 Discord）。
- 網站介面全繁體中文。
- 已驗證事實（2026-07-14 probe）：`https://hkmovie6.com/showing` 帶瀏覽器 UA 回 200，server-rendered；上映電影係 anchor `href="/movie/{uuid}/{URL-encoded 標題}"`；海報圖喺 `https://storage.movie6.com/movie/*.jpg`；頁面有 ld+json。冇公開 API。

---

### Task 1: 分類改名（電影→電影活動）＋ 院線電影保留

**Files:**
- Modify: `scrape.py`（`CATEGORIES`、`CATEGORY_KEYWORDS`、`merge()`）
- Test: `tests/test_scrape.py`

**Interfaces:**
- Consumes: 現有 `categorize(title, default)`、`merge(lists, today)`
- Produces: `merge()` 對 `source == "hkmovie6"` 保留 `category`；`categorize()` 嘅電影 keyword 輸出 `"電影活動"`

- [ ] **Step 1: 改現有 test，令佢反映新命名**

喺 `tests/test_scrape.py` 嘅 `test_categorize()` 度，將電影嗰行由
`== "電影"` 改為 `== "電影活動"`：

```python
    assert scrape.categorize("經典粵語片修復放映", "休閒") == "電影活動"
```

同一 test 內，親子電影優先次序嗰行（電影組排先）改為：

```python
    # 優先次序：親子電影應該歸電影活動（電影組排先）
    assert scrape.categorize("親子電影放映會", "休閒") == "電影活動"
```

- [ ] **Step 2: 新增兩個 test（院線電影保留 + Discord 隔走準備）**

喺 `tests/test_scrape.py` 加：

```python
def test_merge_keeps_cinema_category():
    e = make(id="c", title="反斗奇兵5", category="電影")
    e["source"] = "hkmovie6"
    out = scrape.merge([[e]], today="2026-07-14")
    assert out[0]["category"] == "電影"


def test_merge_cinema_title_with_keyword_not_downgraded():
    # 戲名含「電影」二字，但係 hkmovie6 來源，唔應該變「電影活動」
    e = make(id="c2", title="這部電影很好看", category="電影")
    e["source"] = "hkmovie6"
    out = scrape.merge([[e]], today="2026-07-14")
    assert out[0]["category"] == "電影"
```

注意：`make()` 預設 `source="test"`；上面覆寫成 `"hkmovie6"`。

- [ ] **Step 3: 行 test 確認 fail**

Run: `python -m pytest tests/ -v -k "categorize or cinema"`
Expected 有 fail：
- `test_categorize` fail（電影 keyword 而家仲 return「電影」，未改成「電影活動」）。
- `test_merge_cinema_title_with_keyword_not_downgraded` fail（戲名含「電影」keyword，未有 source 例外時 `categorize()` 會降級成「電影活動」）。
- `test_merge_keeps_cinema_category` 可能一開始已 pass（戲名「反斗奇兵5」唔含 keyword，`categorize()` 會 return default「電影」）——佢係 regression guard，唔係主要 red test。

- [ ] **Step 4: 改 `CATEGORIES` 同 `CATEGORY_KEYWORDS`**

`scrape.py` 頂部：

```python
CATEGORIES = {"體育", "休閒", "大型盛事", "表演藝術", "展覽",
              "電影", "電影活動", "親子"}
```

`CATEGORY_KEYWORDS` 入面現有：
```python
    ("電影", ["電影", "放映", "影展"]),
```
改為：
```python
    ("電影活動", ["電影", "放映", "影展"]),
```

- [ ] **Step 5: 改 `merge()` 令院線電影保留 category**

現有 `merge()` 迴圈內：
```python
            e = dict(e, title=" ".join(e["title"].split()),
                     category=categorize(e["title"], e["category"]),
                     image=e.get("image", ""))
```
改為：
```python
            cat = e["category"] if e.get("source") == "hkmovie6" \
                else categorize(e["title"], e["category"])
            e = dict(e, title=" ".join(e["title"].split()),
                     category=cat,
                     image=e.get("image", ""))
```

- [ ] **Step 6: 行 test 確認 pass**

Run: `python -m pytest tests/ -v`
Expected: 全部 PASS（包括新加嘅兩個 cinema test）。

- [ ] **Step 7: Commit**

```bash
git add scrape.py tests/test_scrape.py
git commit -m "feat: rename 電影 category to 電影活動; keep cinema films"
```

---

### Task 2: hkmovie6 爬蟲

**Files:**
- Create: `scrapers/hkmovie.py`

**Interfaces:**
- Consumes: `scrapers.common.http_get`、`scrapers.common.make_id`
- Produces: `scrapers.hkmovie.SOURCE = "hkmovie6"`；`scrapers.hkmovie.fetch() -> list[dict]`

- [ ] **Step 1: 寫 `scrapers/hkmovie.py`**

```python
import datetime
import urllib.parse

from bs4 import BeautifulSoup

from scrapers.common import http_get, make_id

SOURCE = "hkmovie6"
PAGE_URL = "https://hkmovie6.com/showing"
BASE = "https://hkmovie6.com"
# ponytail: 上映電影冇單一日期，用今日起 30 日滾動窗口避免被剪走
WINDOW_DAYS = 30


def fetch():
    soup = BeautifulSoup(http_get(PAGE_URL).text, "html.parser")
    today = datetime.date.today()
    end = (today + datetime.timedelta(days=WINDOW_DAYS)).isoformat()
    start = today.isoformat()

    movies = {}
    for a in soup.select('a[href^="/movie/"]'):
        href = a.get("href", "")
        parts = href.strip("/").split("/")
        # 期望 ["movie", "{uuid}", "{url-encoded 標題}"]
        if len(parts) < 3 or parts[0] != "movie":
            continue
        uid = parts[1]
        if uid in movies:
            continue
        title = urllib.parse.unquote(parts[2]).strip()
        if not title:
            continue
        img = a.find("img")
        image = ""
        if img is not None:
            image = (img.get("src") or img.get("data-src") or "").strip()
        movies[uid] = {
            "id": make_id(SOURCE, uid),
            "title": title,
            "category": "電影",
            "start": start,
            "end": end,
            "venue": "",
            "url": BASE + href,
            "source": SOURCE,
            "image": image,
        }
    return list(movies.values())
```

- [ ] **Step 2: Live check**

Run:
```bash
python -c "from scrapers import hkmovie; evs = hkmovie.fetch(); print(len(evs)); [print(e['title'], '|', bool(e['image']), '|', e['url']) for e in evs[:8]]"
```
Expected: 印出上映電影數量（正常幾十齣；若接近 179 或有明顯非電影項，代表 selector 撈埋推薦／即將上映，需收窄——例如只揀 `/showing` 主區塊內嘅 anchor，可用 `soup.select("main a[href^='/movie/']")` 或搵包住上映清單嘅 container class 再喺其內 select）。抽一個 `url` 開瀏覽器確認去到電影頁。`image` 若大面積係空，檢查海報係咪 lazy-load（`data-src`／`data-original`）或喺 anchor 外，調整抽 img 嘅位置。

- [ ] **Step 3: Commit**

```bash
git add scrapers/hkmovie.py
git commit -m "feat: hkmovie6 now-showing cinema fetcher"
```

---

### Task 3: 註冊來源 + Discord 隔走電影

**Files:**
- Modify: `scrapers/__init__.py`
- Modify: `scrape.py`（`main()` Discord 推送段）
- Test: `tests/test_scrape.py`

**Interfaces:**
- Consumes: Task 2 嘅 `scrapers.hkmovie`；現有 `find_new`、`push_discord`
- Produces: `FETCHERS` 含 hkmovie；`main()` 推送前隔走 `category == "電影"`

- [ ] **Step 1: 註冊 fetcher**

`scrapers/__init__.py` 現有：
```python
from scrapers import brandhk, lcsd, timable

FETCHERS = [
    (lcsd.SOURCE, lcsd.fetch),
    (timable.SOURCE, timable.fetch),
    (brandhk.SOURCE, brandhk.fetch),
]
```
改為：
```python
from scrapers import brandhk, hkmovie, lcsd, timable

FETCHERS = [
    (lcsd.SOURCE, lcsd.fetch),
    (timable.SOURCE, timable.fetch),
    (brandhk.SOURCE, brandhk.fetch),
    (hkmovie.SOURCE, hkmovie.fetch),
]
```

- [ ] **Step 2: 加 Discord 隔走電影嘅 test**

喺 `tests/test_scrape.py` 加（驗證用嚟決定「推邊啲」嘅 filter 邏輯）：

```python
def test_cinema_excluded_from_discord_push():
    events = [make(id="a", category="體育"),
              make(id="b", title="反斗奇兵5", category="電影"),
              make(id="c", category="展覽")]
    seen = {}
    new = scrape.find_new(events, seen)
    to_push = [e for e in new if e["category"] != "電影"]
    assert {e["id"] for e in to_push} == {"a", "c"}
```

- [ ] **Step 3: 行 test 確認新 test pass（純邏輯，已可通過）**

Run: `python -m pytest tests/ -v -k discord`
Expected: `test_cinema_excluded_from_discord_push` PASS（呢個 test 驗證 filter 表達式本身）。

- [ ] **Step 4: 改 `main()` 推送段真正隔走電影**

`scrape.py` `main()` 現有：
```python
    new = find_new(events, seen)
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
    retry_ids = set()
    if new and webhook and not first_run:
        try:
            push_discord(webhook, new)
            print(f"discord: pushed {len(new)} new events")
        except Exception:
            retry_ids = {e["id"] for e in new}
            print("discord: push failed, will retry next run")
            traceback.print_exc()
```
改為：
```python
    new = find_new(events, seen)
    to_push = [e for e in new if e["category"] != "電影"]
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
```

注意：`retry_ids` 只涵蓋 `to_push`（電影從不推送，唔需要重試）；seen 標記
迴圈不變（照樣 mark 所有 events 包括電影）。

- [ ] **Step 5: 行 test 同全管線**

Run: `python -m pytest tests/ -v`
Expected: 全部 PASS。

Run: `python scrape.py`
Expected: 四行 `來源: N events`（含 `hkmovie6: N events`）+ `total: ...`；`docs/events.json` 重新生成。肉眼檢查 events.json：有 `category == "電影"` 嘅院線戲（有海報 image、url 係 hkmovie6.com/movie/…），原本嗰批文化放映變咗 `category == "電影活動"`。

- [ ] **Step 6: Commit**

```bash
git add scrapers/__init__.py scrape.py tests/test_scrape.py docs/events.json state/seen.json
git commit -m "feat: register hkmovie6 source; exclude cinema films from discord"
```

---

### Task 4: 前端分類掣

**Files:**
- Modify: `docs/index.html`

**Interfaces:**
- Consumes: `docs/events.json`（含 `category == "電影"` 同 `"電影活動"`）
- Produces: 兩個新分類掣 + `META` 條目

- [ ] **Step 1: 加分類掣**

`docs/index.html` 現有分類掣區（`<div class="controls" id="cats">`）內，
現有：
```html
    <button data-c="電影">🎬 電影</button>
    <button data-c="親子">🧸 親子</button>
```
改為：
```html
    <button data-c="電影">🎬 電影</button>
    <button data-c="電影活動">🎞️ 電影活動</button>
    <button data-c="親子">🧸 親子</button>
```

- [ ] **Step 2: 加 `META` 條目**

`docs/index.html` `<script>` 內 `META` 物件，現有：
```javascript
  "電影":     { e:"🎬",  g:"linear-gradient(135deg,#343a40,#868e96)" },
  "親子":     { e:"🧸",  g:"linear-gradient(135deg,#e8590c,#ffa94d)" },
```
改為：
```javascript
  "電影":     { e:"🎬",  g:"linear-gradient(135deg,#c92a2a,#ff6b6b)" },
  "電影活動": { e:"🎞️", g:"linear-gradient(135deg,#343a40,#868e96)" },
  "親子":     { e:"🧸",  g:"linear-gradient(135deg,#e8590c,#ffa94d)" },
```
（院線「電影」改用紅色調突出，文化「電影活動」沿用原本灰調。）

- [ ] **Step 3: 本地 verify**

Run: `python -m http.server 8000 --directory docs`（背景），瀏覽器開 `http://localhost:8000`。
Expected: 見到「🎬 電影」同「🎞️ 電影活動」兩個掣；撳「🎬 電影」淨係院線戲（有海報縮圖）；撳「🎞️ 電影活動」淨係文化放映；搜尋照常。搞掂停 server。

- [ ] **Step 4: Commit**

```bash
git add docs/index.html
git commit -m "feat: 電影 (院線) and 電影活動 category chips"
```

---

### Task 5: 部署 + 端到端驗證

**Files:** 冇新檔案（部署操作）

**Interfaces:**
- Consumes: 成個 repo；remote `origin`（github.com/wyho1029/hk-events）已設定
- Produces: 上線更新 + 確認 hkmovie6 喺 Actions 環境行唔行

- [ ] **Step 1: Push**

```bash
git push origin master
```
Expected: push 成功。

- [ ] **Step 2: 手動觸發 workflow 驗證 hkmovie6 喺雲端 IP 行唔行**

```bash
gh workflow run update-events --repo wyho1029/hk-events
gh run list --workflow=update-events --limit 1
```
等 run 完成（`gh run view <id> --log` 睇 `hkmovie6: N events` 一行）。
Expected: run 成功。**重點**：睇 hkmovie6 係咪攞到戲（N > 0）定係同 Timable 一樣被擋（FAILED → fallback）。兩種都唔會 fail 個 job，但要記錄實況。

- [ ] **Step 3: 驗證 live 網站**

```bash
gh api "repos/wyho1029/hk-events/pages" --jq .html_url
```
瀏覽器開 URL，撳「🎬 電影」掣。
Expected: 若 Step 2 hkmovie6 成功，見到院線戲配海報；若被擋，電影分類可能係空（本地 push 上去嗰批 events.json 有戲，但 Actions 重爬會覆寫成 fallback／空——如被擋，喺 README 記低「電影來源同 Timable 一樣需本地更新」）。

- [ ] **Step 4: 按實況更新 README（如 hkmovie6 喺 Actions 被擋）**

若 Step 2 顯示 hkmovie6 喺 Actions 被擋，喺 `README.md` 嘅「已知限制」
段落加一句：hkmovie6（電影來源）同 Timable 一樣喺 GitHub Actions 雲端 IP
可能被擋，屆時電影資料需喺本地行 `python scrape.py` 更新。若成功則唔使改。

```bash
git add README.md
git commit -m "docs: note hkmovie6 actions limitation" && git push origin master
```
（若 hkmovie6 喺 Actions 正常，跳過呢步。）

- [ ] **Step 5: 完成**

向用戶匯報：新「電影」分類上線情況、hkmovie6 喺 Actions 行唔行、電影唔推 Discord 已生效。
