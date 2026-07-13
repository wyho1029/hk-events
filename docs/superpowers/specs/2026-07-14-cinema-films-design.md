# 戲院上畫電影分類 — 設計文件

日期：2026-07-14
狀態：已獲用戶批准

## 目標

將現有「電影」分類（其實係康文署嘅文化放映活動：電影節、天文電影、
電影資料館展覽）改名做「電影活動」，並新增一個真正嘅「電影」分類，
收錄香港戲院正在上映嘅院線電影。資料嚟自 hkmovie6.com。

## 背景（實測 2026-07-14）

- 現有「電影」分類 32 個全部係文化放映活動，冇一齣係戲院上畫商業電影。
- hkmovie6.com/showing 用瀏覽器 UA 攞到（200，server-rendered），內含
  上映電影連結 `/movie/{uuid}/{標題}`（標題 URL-encoded）同海報圖
  `https://storage.movie6.com/movie/*.jpg`。
- 冇公開 API，靠爬 HTML；改版風險同 Timable 一樣，靠 fetcher 隔離處理。

## 架構改動

沿用現有管線（scrapers → merge → events.json → 靜態站 → Discord），
只加一個爬蟲同少量 wiring：

### 1. 新爬蟲 `scrapers/hkmovie.py`

- `SOURCE = "hkmovie6"`；`fetch() -> list[dict]`（統一 event schema）。
- 由 `/showing` 頁抽每齣上映電影：標題、電影頁 URL、海報 image。
- 因為院線電影冇單一日期／單一戲院，映射如下：
  - `start` = 今日（`datetime.date.today()`）
  - `end` = 今日 + 30 日（滾動窗口，避免被 merge 嘅「已完結」邏輯剪走；
    落畫後下次爬取自然唔再出現）
  - `venue` = ""（喺多間戲院）
  - `url` = hkmovie6 該電影頁（去到睇晒場次）
  - `category` = "電影"
  - `image` = 海報 URL
- 去重：同一電影可能喺頁面出現多次，用 movie uuid（連結入面）做
  `make_id` 嘅 key，於 fetcher 內先去重。

### 2. `scrape.py` 分類同常量

- `CATEGORIES` 加入 `"電影"` 同 `"電影活動"`。
- `CATEGORY_KEYWORDS` 現有嘅 `"電影"` 條目改為輸出 `"電影活動"`
  （keyword：電影、放映、影展 不變）。
- 院線電影由爬蟲直接標 `category="電影"`；因為 `categorize()` 會用
  keyword 覆寫，需要確保院線電影唔會被降級。做法：`categorize()` 對
  已經係 `"電影"` 或 `"電影活動"` 嘅唔再改（或者院線電影標題通常唔含
  keyword 但為穩陣起見，categorize 對院線 source 保持原 category）。
  實作採用：`merge()` 對 `source == "hkmovie6"` 嘅保留 `"電影"`，
  唔行 `categorize()`。

### 3. Discord 唔推電影

- 推送前由 `new` 隔走 `category == "電影"`：
  `new_for_discord = [e for e in new if e["category"] != "電影"]`。
- `seen` 照樣記錄所有 events（包括電影），令院線電影永不經 Discord，
  只喺網站顯示。首次 seed／retry 語義不變。

### 4. 前端 `docs/index.html`

- 分類掣加 `🎬 電影`（院線）同 `🎞️ 電影活動`。
- `META` 加兩個分類嘅 emoji／漸變色（電影活動沿用電影灰調，院線電影
  另一色以資區別）。
- 其餘 hero／列表／縮圖邏輯不變。

## 資料流

hkmovie6 fetcher（category=電影）＋ 其餘三來源
  → merge：院線電影保留「電影」，其餘照 categorize（電影 keyword→電影活動）
  → events.json
  → 網站顯示（8 個分類）
  → Discord 推送（隔走電影）

## 錯誤處理

- hkmovie6 fetcher 失敗：同其他 fetcher 一樣，用 previous_events 回退，
  唔影響其他來源。
- 若 hkmovie6 喺 GitHub Actions 雲端 IP 被擋（同 Timable 情況），
  自動回退，README 記低。

## 測試

- 更新現有 `test_categorize`：電影 keyword 應輸出 `"電影活動"`。
- 新增測試：`merge()` 對 `source=="hkmovie6"` 嘅 event 保留 `category=="電影"`，
  唔會被 categorize 降級。
- 新增測試：Discord 推送隔走 `category=="電影"`（`new_for_discord` 邏輯）。
- hkmovie 爬蟲照現有慣例用 live smoke check，唔寫 fixture。

## 已知風險

1. hkmovie6 改版令 fetcher 失效——fetcher 隔離處理，回退舊資料。
2. hkmovie6 喺 Actions 雲端 IP 可能被擋——實測部署環境先知，最壞情況
   同 Timable 一樣持續用舊資料，README 記低。
3. 院線電影用滾動 30 日窗口，落畫嘅戲要下次爬取先消失——可接受。
