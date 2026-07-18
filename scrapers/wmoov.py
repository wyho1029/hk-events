import datetime

from bs4 import BeautifulSoup

from scrapers.common import http_get, make_id

SOURCE = "wmoov"
PAGE_URL = "https://wmoov.com/movie/showing"
BASE = "https://wmoov.com"
# ponytail: 上映電影冇單一日期，用今日起 30 日滾動窗口
WINDOW_DAYS = 30


def fetch():
    soup = BeautifulSoup(http_get(PAGE_URL).text, "html.parser")
    today = datetime.date.today()
    start = today.isoformat()
    end = (today + datetime.timedelta(days=WINDOW_DAYS)).isoformat()

    movies = {}
    # 真正「即日上映」grid 喺 .showing_movie_list_b，每齣戲一個 div.each
    # （h3 有戲名，poster_s 有海報，div.rating 有會員評分）；
    # 頂部 nav 下拉包埋百幾齣不日上映，所以唔掃全頁
    for card in soup.select("div.showing_movie_list_b div.each"):
        a = card.select_one('h3 a[href*="/movie/details/"]')
        if a is None:
            continue
        href = a.get("href", "")
        mid = href.rstrip("/").split("/")[-1]
        title = " ".join(a.get_text(" ", strip=True).split())
        if not mid.isdigit() or not title or mid in movies:
            continue
        image = ""
        img = card.select_one("div.poster_s img")
        if img is not None:
            src = (img.get("data-src") or img.get("src") or "").strip()
            if src.startswith("/"):
                src = BASE + src
            image = src
        rating = ""
        r = card.select_one("div.rating b")
        if r is not None:
            rating = r.get_text(strip=True)
        movies[mid] = {
            "id": make_id(SOURCE, mid),
            "title": title,
            "category": "電影",
            "start": start,
            "end": end,
            "venue": "",
            "url": BASE + href,
            "source": SOURCE,
            "image": image,
            "rating": rating,
        }
    return list(movies.values())
