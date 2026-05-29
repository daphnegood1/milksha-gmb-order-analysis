# 臺南迷客夏 GMB 外帶外送分析

這個專案產出一個靜態網頁，用來盤點臺南市迷客夏門市的 Google 商家連結、外帶/外送狀態、服務商與證據來源。

## 資料來源

- 迷客夏官方門市頁：<https://www.milksha.com/store_detail.php?uID=1>
- Google Places API：若設定 `GOOGLE_MAPS_API_KEY`，資料產生腳本會優先補上 `placeId`、`googleMapsUri`、`businessStatus`、`takeout`、`delivery`
- 公開資料備援：Nidin 官方點餐資料、Footinder 平台交叉比對、既有人工紀錄

服務商判定不會直接等同 GMB 官方欄位。網頁會以「證據來源」與「信心等級」標示資料來源差異。

## 重新產生資料

```powershell
python tools\build_tainan_dataset.py
```

若目前沒有 Google API key，腳本仍會使用 `data/source-stores.csv` 產出臺南專用資料。

```powershell
$env:GOOGLE_MAPS_API_KEY="你的 API key"
python tools\build_tainan_dataset.py
```

輸出檔案：

- `data/stores.json`
- `data/stores.csv`
- `data/summary.json`

## 本機預覽

```powershell
python -m http.server 4173
```

開啟 <http://localhost:4173>。
