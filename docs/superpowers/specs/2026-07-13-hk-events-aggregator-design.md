# 香港活動整合網站 — 設計文件

日期：2026-07-13
狀態：已獲用戶批准（方案 A）

## 目標

一個自動更新嘅網站，整合香港即將舉行嘅**體育、休閒、大型盛事**活動；
排除娛樂圈內容（演唱會、明星見面會等）。有新活動時推送 Discord 通知。
全自動、全免費、零 server 維護。

## 架構

```
GitHub Actions（每日 09:00 HKT cron）
  → scrape.py 逐個跑 fetcher（LCSD / URBTIX / Cityline / KKTIX / Timable / HKTB）
  → 合併去重 → keyword 過濾娛樂圈內容 → docs/events.json
  → 對比 state/seen.json → 新活動 post 去 Discord webhook
  → commit + push → GitHub Pages 自動更新網站
```

## 組件

### 1. 爬蟲（`scrapers/`，Python）

每個來源一個獨立 module，統一輸出格式：

```json
{ "id": "...", "title": "...", "category": "體育|休閒|大型盛事",
  "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "venue": "...",
  "url": "...", "source": "..." }
```

- `id` 由 source + 活動 URL/編號 hash 而成，用嚟去重同記錄「已見過」。
- 每個 fetcher 獨立 try/except：一個來源失敗（網站改版、anti-bot），
  log 低、跳過，唔影響其他來源；該來源用返上次成功嘅資料。
- 全部 fetcher 都失敗先算 job 失敗。

### 2. 過濾

Keyword 規則排除娛樂圈活動（演唱會、音樂會、fan meeting、明星等字眼），
白名單分類：體育／休閒／大型盛事。規則放喺一個易改嘅列表度。

### 3. 網站（`docs/index.html`）

- 靜態一頁式，vanilla JS fetch `events.json`，冇 build step。
- 繁體中文介面；活動按日期排序；分類篩選掣；文字搜尋。
- GitHub Pages serve `docs/` 目錄。

### 4. Discord 推送

- `state/seen.json` 記錄已推送嘅 event id。
- 每次跑完，凡係新 id 嘅活動，一次過用一條 embed 訊息推去
  `DISCORD_WEBHOOK_URL`（GitHub Actions secret）。
- 冇新活動就唔推。推送失敗唔阻網站更新。

### 5. 自動化（`.github/workflows/`）

- 每日 09:00 HKT（01:00 UTC）cron + 可手動觸發。
- 跑 scraper → commit `docs/events.json` 同 `state/seen.json` → push。

## 錯誤處理

- Fetcher 層：獨立 try/except，失敗唔擴散。
- Discord 層：推送失敗只 log，唔 fail job。
- 資料層：events.json 寫入前驗 schema，格式錯嘅活動棄掉並 log。

## 測試

一個 smoke test：驗 events.json schema 同娛樂圈過濾邏輯。
唔為每個爬蟲寫 fixture 套件——爬蟲壞源於對方網站改版，fixture 驗唔到。

## 已知風險

1. **URBTIX / Cityline 有 anti-bot 保護**，GitHub Actions IP 可能被擋。
   實施時逐個試；爬唔到就跳過該來源或者搵公開 API/RSS 替代。
2. 需要用戶提供 Discord webhook URL（Server 設定 → 整合 → Webhook）。
3. 需要開 GitHub repo 並啟用 Pages + Actions。

## 用戶要做嘅嘢

1. 開 GitHub repo（如未有帳號要開埋）。
2. 提供 Discord webhook URL，設做 repo secret `DISCORD_WEBHOOK_URL`。
