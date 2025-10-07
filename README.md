# ⚔️ RO 拍賣市場數據自動化分析 (ro_auction)

這是一個用於追蹤並分析《仙境傳說》（Ragnarok Online）遊戲中，特定高價物品在遊戲拍賣行市場價格趨勢的自動化專案。

本專案使用 **Python/Selenium** 進行數據爬取，並透過 **GitHub Actions** 實現每小時自動執行、數據同步、圖表繪製及最終發佈至 **GitHub Pages** 的全自動化流程。

---

## 📈 市場趨勢圖表

點擊下方連結，查看最新的市場數據分析圖表。圖表內容**每小時會自動更新一次**：

### [📊 立即查看：神之金屬市場分析圖表](https://nyto9999.github.io/ro_auction/%E7%A5%9E%E4%B9%8B%E9%87%91%E5%B1%AC_%E5%B8%82%E5%A0%B4%E5%88%86%E6%9E%90.html)

---

## ⚙️ 專案技術與結構

### 自動化流程

本專案的自動化流程確保數據持續更新、圖表及時生成並發佈：

1. **數據收集：** 本地 `main_scraper.py` 每小時運行，爬取最新的拍賣數據並生成 CSV 彙總檔案。
2. **數據同步：** 最新 CSV 數據被自動提交並推送到 `main` 分支。
3. **圖表生成：** GitHub Actions（定義於 `.github/workflows/schedule_plot.yml`）在數據同步後，於每小時的 5 分鐘觸發運行。
4. **繪圖執行：** Action 執行 `plot.py` 生成互動式 HTML 圖表。
5. **公開：** GitHub Pages 監聽 `main` 分支變動，自動發佈最新的 HTML 文件到公開網址。

### 核心檔案

| 檔案名稱 | 說明 |
| :--- | :--- |
| `main.py` | 核心**爬蟲**邏輯。負責網頁爬取、數據處理、生成 CSV 數據，並內建 Git 推送功能。 |
| `plot.py` | 核心**繪圖**邏輯。負責讀取 CSV 數據，使用 Plotly 繪製精美互動式 HTML 圖表。 |
| `.github/workflows/schedule_scraper.yml` | GitHub Actions 工作流程定義，設定每小時自動運行爬蟲並同步數據。 |
| `.github/workflows/schedule_plot.yml` | GitHub Actions 工作流程定義，設定每小時自動繪製圖表。 |
| `index.html` | 網站的歡迎頁面，包含圖表連結。 |
| `神之金屬_市場分析.html` | 最終生成的互動式 Plotly 圖表文件。 |

---

## 🛠️ 如何自行部署 (For Developers)

如果您想複製此專案，追蹤不同的道具或伺服器，您需要以下設置：

### 1. 設置登入機密 (Secrets)

由於爬蟲需要登入，請在您的 GitHub Repository **`Settings -> Secrets -> Actions`** 中，添加以下兩個 **Repository Secrets**，以安全地傳遞登入憑證：

| Secret 名稱 | 說明 |
| :--- | :--- |
| `AUCTION_USERNAME` | 拍賣網站的登入帳號。 |
| `AUCTION_ID` | 拍賣網站的登入密碼。 |

### 2. 核心依賴

以下是您的 Python 專案所需的函式庫，這些都會透過 Actions YAML 文件自動安裝：

```bash
# 爬蟲與數據處理核心
pip install pandas tabulate undetected-chromedriver selenium 

# 圖表繪製核心
pip install plotly
