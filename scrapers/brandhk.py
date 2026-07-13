import re

from bs4 import BeautifulSoup

from scrapers.common import http_get, make_id

SOURCE = "盛事之都"
PAGE_URL = "https://www.brandhk.gov.hk/zh-hk/盛事之都/香港最新活動"
DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")


def fetch():
    soup = BeautifulSoup(http_get(PAGE_URL).text, "html.parser")
    # 活動圖片喺 event-title block 外面，用 data-title 對返標題
    images = {img.get("data-title", "").strip(): img.get("data-img", "")
              for img in soup.select("a.event-lazy-img[data-img]")}
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
            "image": images.get(title, ""),
        })
    return events
