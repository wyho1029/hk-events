"""博客來中文書月暢銷榜 Top 20（排除漫畫）→ docs/books.json。

同 scrape.py（活動）分開跑：書籍有排名／作者／價錢、無日期、月更。
排除漫畫用「總榜減去漫畫榜」：多抓一版漫畫/圖文書榜做黑名單，可靠過猜關鍵字。
"""
import datetime
import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
BOOKS_PATH = ROOT / "docs" / "books.json"

TOTAL_URL = "https://www.books.com.tw/web/sys_saletopb/books/"
MANGA_URL = "https://www.books.com.tw/web/sys_saletopb/books/16/"  # 漫畫/圖文書
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}
HK_TZ = datetime.timezone(datetime.timedelta(hours=8))
TOP_N = 20


def _norm_title(t):
    """去標點空白轉小寫，做跨榜同名比對。"""
    return re.sub(r"[\s　：:，,、（）()\[\]【】「」『』《》〈〉．·.\-‧—–_/]",
                  "", t).lower()


def _price(li):
    el = li.select_one("li.price_a")
    if el is None:
        return ""
    bolds = el.find_all("b")
    if len(bolds) >= 2:
        return f"NT${bolds[1].get_text(strip=True)}"
    return el.get_text(strip=True).replace("優惠價：", "").strip()


def parse_list(html):
    """一個榜頁 → list of {rank,title,author,price,url,image}（rank 依榜序）。"""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for li in soup.select("li.item"):
        a = li.select_one("div.type02_bd-a h4 a")
        if a is None or not a.get_text(strip=True):
            continue
        author_el = li.select_one("ul.msg li a")
        img = li.select_one("img.cover")
        image = ""
        if img is not None:
            image = (img.get("data-original") or img.get("src") or "").strip()
            if not image.startswith("http"):
                image = ""
        out.append({
            "rank": len(out) + 1,
            "title": a.get_text(strip=True),
            "author": author_el.get_text(strip=True) if author_el else "",
            "price": _price(li),
            "url": a.get("href", "").split("?")[0],
            "image": image,
        })
    return out


def fetch_list(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.encoding = "utf-8"
    r.raise_for_status()
    return parse_list(r.text)


def build(total, manga, top_n=TOP_N):
    """由總榜剔走漫畫榜命中嘅書，取 top_n 重新編號。"""
    banned = {_norm_title(b["title"]) for b in manga}
    out = []
    for b in total:
        if _norm_title(b["title"]) in banned:
            continue
        out.append({**b, "rank": len(out) + 1})
        if len(out) >= top_n:
            break
    return out


def main():
    try:
        total = fetch_list(TOTAL_URL)
    except Exception as e:
        print(f"[!] 博客來總榜抓取失敗，保留舊 books.json：{e}")
        return
    if not total:
        print("[!] 博客來總榜空，保留舊 books.json")
        return
    try:
        manga = fetch_list(MANGA_URL)
    except Exception as e:
        print(f"[!] 漫畫榜抓取失敗，當空黑名單（可能有漫畫漏網）：{e}")
        manga = []

    books = build(total, manga)
    month = datetime.datetime.now(HK_TZ).strftime("%Y-%m")
    BOOKS_PATH.parent.mkdir(exist_ok=True)
    BOOKS_PATH.write_text(
        json.dumps({"updated": month, "books": books},
                   ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"total {len(total)}, manga {len(manga)} "
          f"-> {len(books)} books ({month}) -> {BOOKS_PATH}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
