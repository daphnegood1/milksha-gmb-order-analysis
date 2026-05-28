# 茶聚 GMB 點餐服務統計

這個專案用來整理台灣茶聚 CHAGE 門市的 Google 商家檔案點餐服務資訊，並發布成 GitHub Pages 靜態網站。

## 目前資料狀態

- 官方門市清單來自茶聚官網「門市據點」。
- GMB 欄位先建立 Google Maps 查詢連結與查核狀態。
- 使用者提供的「茶聚CHAGE永康中華店」已依截圖人工標註 foodpanda、Uber Eats、lin.ee。
- 其他門市若尚未能透過瀏覽器逐店確認，會標示為「待查核」，不列入已確認服務商統計。

## 更新資料

```powershell
& "C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" tools\fetch_official_stores.py
```

產出：

- `data/stores.json`
- `data/stores.csv`

## GitHub Pages

本專案是純靜態網站，GitHub Pages 可直接使用 `main` branch root 目錄發布。
