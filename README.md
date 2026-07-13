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
    python -m pytest tests/   # 行測試（需要另外 pip install pytest）

## 設定

- Repo secret `DISCORD_WEBHOOK_URL`：Discord webhook。
- GitHub Pages：Settings → Pages → Deploy from branch → `master` / `docs`。

## 已知限制

Timable 喺 GitHub Actions 嘅雲端 IP 會被擋（HTTP 403），所以每日自動更新時
Timable 來源會自動沿用上次成功嘅資料；想更新 Timable 資料要喺本地行一次
`python scrape.py`。將來可研究替代方案。
