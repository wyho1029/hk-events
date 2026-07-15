import datetime

from bs4 import BeautifulSoup

from scrapers.common import http_get, make_id

SOURCE = "wmoov"
PAGE_URL = "https://wmoov.com/movie/showing"
BASE = "https://wmoov.com"
# ponytail: 同 hkmovie 一樣，上映電影用今日起 30 日滾動窗口
WINDOW_DAYS = 30


def fetch():
    soup = BeautifulSoup(http_get(PAGE_URL).text, "html.parser")
    today = datetime.date.today()
    start = today.isoformat()
    end = (today + datetime.timedelta(days=WINDOW_DAYS)).isoformat()

    movies = {}
    # 真正「即日上映」grid 喺 .showing_movie_list_b（實測 31 齣）；
    # 頂部 nav 下拉包埋 110 齣不日上映，所以唔掃全頁。
    # 每齣戲喺 grid 出現兩次（海報連結得圖、文字連結得名），按 id 合併
    for a in soup.select(
            'div.showing_movie_list_b a[href*="/movie/details/"]'):
        href = a.get("href", "")
        mid = href.rstrip("/").split("/")[-1]
        if not mid.isdigit():
            continue
        m = movies.setdefault(mid, {
            "id": make_id(SOURCE, mid),
            "title": "",
            "category": "電影",
            "start": start,
            "end": end,
            "venue": "",
            "url": BASE + href,
            "source": SOURCE,
            "image": "",
        })
        title = " ".join(a.get_text(" ", strip=True).split())
        if title and not m["title"]:
            m["title"] = title
        img = a.find("img")
        if img is not None and not m["image"]:
            src = (img.get("data-src") or img.get("src") or "").strip()
            if src.startswith("/"):
                src = BASE + src
            m["image"] = src
    return [m for m in movies.values() if m["title"]]
