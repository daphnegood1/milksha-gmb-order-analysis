# 迷客夏 GMB 點餐服務統計

這是一個 GitHub Pages 靜態網站，用來整理迷客夏台灣門市的 Google 商家檔案連結、點餐外帶 / 外送服務商與查核狀態。

## 資料來源

- 官方台灣門市列表：<https://www.milksha.com/store_detail.php?uID=1>
- 原需求指定入口：<https://www.milksha.com/en/store_detail.php?uID=22>

`uID=22` 是查詢介面；`uID=1` 是官方頁面中實際渲染台灣門市卡片的來源。

## 更新資料

```powershell
python tools\fetch_official_stores.py
python tools\audit_order_providers.py --workers 10
python tools\audit_nidin_order.py
```

輸出：

- `data/stores.json`
- `data/summary.json`
- `data/audit-samples.json`
- `data/stores.csv`

## 查核狀態

- `confirmed`: 已取得官方頁提供的 Google Maps / GMB 連結。
- `no_gmb_found`: 找不到 Google 商家檔案。
- `closed_or_moved`: 歇業或搬遷。
- `unavailable_or_blocked`: Google 限制或頁面無法讀取。
- `needs_manual_review`: 需要人工開啟商家檔案確認。

Google 商家檔案的點餐按鈕若受自動化限制，資料不猜測，會保留為未確認。

## 查核來源

- 迷客夏官方門市頁：門市母體與 Google Maps 連結。
- 迷客夏官方 Nidin 點餐 API：確認官方線上點餐、自取外帶與 Nidin 外送條件。
- Footinder 店家頁：交叉比對 foodpanda、Uber Eats、lin.ee 等外送供應商。
- 網站統計將外帶服務商與外送服務商分開計算；`providerCounts` 僅保留為總覽相容欄位。

若 Nidin 與 Footinder 都沒有足夠資料，該門市仍標為需人工確認。

## 本機預覽

```powershell
python -m http.server 4173
```

開啟 <http://localhost:4173>。
