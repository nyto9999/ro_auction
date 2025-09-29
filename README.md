# ⚔️ RO 拍賣市場數據自動化分析 (ro_auction)

這是一個用於追蹤並分析《仙境傳說》（Ragnarok Online）遊戲中，特定高價物品在遊戲拍賣行市場價格趨勢的專案。

數據透過本地排程自動爬取，並使用 **GitHub Actions** 進行定時繪圖，最終透過 **GitHub Pages** 公開發佈。

---

## 📈 市場趨勢圖表

點擊下方連結，查看最新的市場數據分析圖表。圖表內容每小時會自動更新一次：

### [📊 立即查看：神之金屬市場分析圖表](https://nyto9999.github.io/ro_auction/%E7%A5%9E%E4%B9%8B%E9%87%91%E5%B1%AC_%E5%B8%82%E5%A0%B4%E5%88%86%E6%9E%90.html)

---

## ⚙️ 專案技術與結構

### 自動化流程

1.  **數據收集：** 本地 `main_scraper.py` 每小時運行，爬取最新的拍賣數據並生成 CSV 彙總檔案。
2.  **數據同步：** 最新 CSV 數據被自動提交並推送到 `main` 分支。
3.  **圖表生成：** GitHub Actions（定義於 `.github/workflows/schedule_plot.yml`）每小時的 5 分鐘觸發運行。
4.  **發佈：** Action 執行 `plot.py` 生成 HTML 圖表，並自動提交到 `main` 分支。
5.  **公開：** GitHub Pages 監聽 `main` 分支變動，自動發佈最新的 HTML 文件到公開網址。

### 核心檔案

| 檔案名稱 | 說明 |
| :--- | :--- |
| `main_scraper.py` | 負責網頁爬取與數據處理，生成 CSV 數據。 |
| `plot.py` | 負責讀取 CSV 數據，使用 Plotly 繪製互動式 HTML 圖表。 |
| `schedule_plot.yml` | GitHub Actions 工作流程定義，設定每小時自動繪圖。 |
| `index.html` | 網站的歡迎頁面，包含圖表連結。 |
| `神之金屬_市場分析.html` | 最終生成的互動式圖表文件。 |