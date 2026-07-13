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
    # 頂部 nav「即日上映」下拉選單撈埋全站電影目錄(實測 178 齣，含已落畫/未上映)；
    # 真正「即日上映」清單淨係喺 div.shows 入面(實測 12 齣，同 og:description 吻合，
    # 點「不日上映」分頁會跳去 /coming 獨立頁面，證實 div.shows 冇被截斷)
    for a in soup.select('div.shows a[href^="/movie/"]'):
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
            # src 係佔位圖(moviePosterPH4.png)，真正海報喺 srcset 度先有；
            # srcset 入面啲 URL 本身帶 comma(f=auto,q=75,w=500)，唔可以用
            # comma 分割，改用空白分割揀返以 http 開頭嘅 token
            srcset = (img.get("srcset") or "").strip()
            if srcset:
                urls = [p for p in srcset.split() if p.startswith("http")]
                image = urls[-1] if urls else ""
            else:
                image = (img.get("data-src") or img.get("src") or "").strip()
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
