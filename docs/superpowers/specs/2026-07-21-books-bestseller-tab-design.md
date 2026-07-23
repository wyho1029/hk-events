# 「書籍」暢銷榜 tab — 設計文件

日期：2026-07-21
狀態：已獲用戶批准

## 目標

喺 HK_Leisure 活動網站加一個「📚 書籍」分類 tab，列出當月博客來中文書
暢銷榜 Top 20，**排除漫畫**，每本連去博客來商品頁。純網站顯示，唔推 Discord。

## 背景（實測 2026-07-21）

- 博客來中文書總榜 `https://www.books.com.tw/web/sys_saletopb/books/`：
  server-rendered HTML，`li.item` 容器，內含 `div.type02_bd-a`（`h4 a`＝
  書名＋商品頁 URL；`ul.msg`＝作者、優惠價）同 `img.cover[data-original]`
  （封面圖，getImage URL，實測 HEAD 200）。一頁 Top 100。
- 總榜**混咗漫畫**：實測 Top 30 有 5 本漫畫（鏈鋸人、鬼滅之刃特裝版等）。
- 博客來「漫畫/圖文書」分類榜 `.../books/16/`：同一結構，Top 100。
- 減法排除實測：總榜 Top 30 命中漫畫榜 5 本全部剔走，賸低完全乾淨
  （投資理財／語言／心理／傳記，冇漏網）。
- 舊 project `AI/eBook/monthly_bestseller/monthly_bestseller.py` 有可重用嘅
  博客來爬蟲同 `normalize_title()` 正規化邏輯，直接借用。
- 書籍資料同活動 event schema 唔夾（有排名／作者／價錢、無日期、月更），
  所以另開一條線，唔塞入 events.json。

## 架構

沿用「靜態 JSON → 前端渲染」模式，但書籍**獨立於活動管線**：

```
books.py（新，獨立於 scrape.py）
  → 抓總榜 + 漫畫榜 → 減法排除漫畫 → Top 20 重新編號
  → docs/books.json
前端 index.html
  → 「📚 書籍」掣 → fetch books.json → 渲染排行榜列表
GitHub Actions
  → 現有 workflow 加一個 step 跑 books.py（books.json 冇變就唔 commit）
```

### 1. 新檔 `books.py`（repo 根，同 scrape.py 平級）

- `SOURCE = "博客來"`；純標準庫 + requests + beautifulsoup4（現有依賴）。
- `HEADERS`：Chrome UA + `Accept-Language: zh-TW`。
- `_norm_title(t)`：借用舊 project 正規化（去標點空白轉小寫）做同名比對。
- `fetch_list(url) -> list[dict]`：由一個榜頁抽每本書
  `{rank, title, author, price, url, image}`：
  - 掃 `li.item`；`div.type02_bd-a h4 a` 攞書名同 URL（缺就跳過）。
  - 作者：`ul.msg li a` 第一個。
  - 價錢：`li.price_a`；兩個 `<b>` 時取第二個做「NT${n}」，否則清理文字。
  - 封面：`img.cover` 嘅 `data-original`（缺就 `src`），要 `http` 開頭。
  - `rank` = 喺榜上嘅次序（1-based）。
- `TOTAL_URL = ".../books/"`；`MANGA_URL = ".../books/16/"`。
- `EXCLUDE_KEYWORDS`：語言考試／語言學習／教科書類（多益/TOEIC/IELTS/雅思/
  托福/TOEFL/檢定/單字/題庫/文法/英語/英文/日語/日文/韓語/韓文/會話/口說/
  發音），`is_excluded(title)` 小寫 substring 比對。
- `build(total, manga, top_n=20) -> list[dict]`：
  - `banned = {_norm_title(b["title"]) for b in manga}`。
  - 由 total 順序剔走 `_norm_title in banned` **或** `is_excluded(title)`，
    取前 `top_n`，重新編 `rank`。
- `main()`：
  - `total = fetch_list(TOTAL_URL)`；抓唔到或空 → 保留舊 books.json，
    印警告後 `return`（唔覆蓋、唔 raise）。
  - `manga = fetch_list(MANGA_URL)`；抓唔到 → `manga = []`（唔剔，寧濫毋缺，
    但唔應該當失敗，因為漫畫榜掛咗唔代表總榜唔可用）。
  - `books = build(total, manga)`。
  - 寫 `docs/books.json`：`{"updated": "YYYY-MM"(HK 時區), "books": books}`，
    `ensure_ascii=False, indent=1`。

### 2. 前端 `docs/index.html`

- 分類列 `#cats` 加 `<button data-c="書籍">📚 書籍</button>`（放喺尾，休閒之後）。
- `META` 加 `"書籍": { e:"📚", g:"linear-gradient(135deg,#5f3dc4,#9775fa)" }`。
- 新全域 `let BOOKS = [];`；fetch `events.json` 之後另外
  `fetch("books.json")` 填 `BOOKS`（失敗唔阻活動顯示）。
- `render()` 入面：`cat === "書籍"` 時行獨立分支——
  - 收起 `#feat`、`#films`、`#list`（清空）；日期篩選 `when` 對書籍無意義，忽略。
  - 渲染書榜落 `#list`（重用容器）：每行一張 `.bk` 卡，
    `#排名` + 封面縮圖 + 書名（serif）+「作者｜定價｜博客來」，整行連去商品頁。
  - `BOOKS` 空 → `#empty` 顯示「暫時攞唔到書籍榜」。
- 樣式 `.bk`：沿用暖色雜誌風；`.bk .rank` terracotta serif 大字（~26px）；
  封面 `.bk .cover` 直度縮圖（約 46×66，`object-fit:cover`，warm 邊框）。

### 3. GitHub Actions

- 現有 `.github/workflows/update.yml` 加一個 step：`python books.py`
  （喺 `python scrape.py` 之後），commit step 加埋 `docs/books.json`。
- books.py 3× 日跑冇問題（榜月更、冇變就唔 commit）；博客來 WAF／Actions IP
  風險同 Timable 一樣，抓唔到就保留舊檔。

## 資料格式

`docs/books.json`：
```json
{
  "updated": "2026-07",
  "books": [
    {"rank": 1, "title": "臺灣漫遊錄", "author": "楊双子",
     "price": "NT$300", "url": "https://www.books.com.tw/products/0010852315",
     "image": "https://im2.book.com.tw/image/getImage?i=...0010852315.jpg&w=150&h=150"}
  ]
}
```

## 錯誤處理

- 總榜抓取失敗／空 → 保留舊 books.json，唔覆蓋。首次冇舊檔就唔寫（前端顯示空狀態）。
- 漫畫榜抓取失敗 → 當空黑名單（可能有漫畫漏網，可接受；好過成個榜唔出）。
- 前端 books.json 缺失／fetch 失敗 → 書籍分支顯示空狀態，唔影響其他分類。

## 測試

- `tests/test_books.py`：
  - `build()` 剔走漫畫（total 含一本漫畫榜出現嘅書 → 結果冇咗、rank 連續）。
  - `build()` top_n 上限同重新編號正確。
  - `_norm_title()` 對標點／空白差異都比對到（同名不同標點視為同書）。
  - 用細段 fixture HTML 測 `fetch_list()` 解析（書名/作者/價錢/封面/rank）。
- books.py 對真站做一次 live smoke（唔入 CI fixture），確認總榜/漫畫榜仲 parse 到。
- 前端 Playwright：撳「📚 書籍」→ 出到榜、封面 load 到、書名冇漫畫樣本、
  排名連續、整行連去博客來。

## 已知風險

1. 博客來改版令 selector 失效 → books.py fetch 失敗保留舊檔，同 Timable 一樣靠
   偶爾人手更新。
2. 博客來 WAF 喺 Actions 雲端 IP 擋（總榜列表頁未必似商品頁咁敏感，實測部署先知）
   → 最壞情況同 Timable，持續用舊 books.json。
3. 漫畫減法靠「總榜書名 = 漫畫榜書名」同名比對；若同一本書兩榜書名寫法差好遠
   會漏（實測 Top 30 全中，風險低）。

## 明確唔做（YAGNI）

- 唔推 Discord（用戶指定純網站顯示）。
- 唔做 Z-Library 下載、Telegram、Obsidian（舊 project 嘅嘢，唔搬過嚟）。
- 唔做內容簡介 enrich（要逐本入商品頁避 WAF，慢且脆，榜單顯示唔需要）。
- 單一來源博客來，唔做多來源合併（日後想再擴充）。
