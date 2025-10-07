# 檔案: main_scraper.py (已優化為 GitHub Actions 環境)

from datetime import datetime
import os
import undetected_chromedriver as uc
import time
import subprocess 
import re
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException


# ----------------- 環境變數 (直接從 Actions Secrets 讀取) -----------------

# 這些變數會直接從 GitHub Actions 的 'env:' 區塊或系統環境變數中讀取
# 確保您已在 Actions YAML 中設定 AUCTION_USERNAME 和 AUCTION_ID
YOUR_USERNAME = os.getenv("AUCTION_USERNAME") 
YOUR_ID = os.getenv("AUCTION_ID")

# 檢查變數是否為空，在 Actions 執行時這是必要的安全檢查
if not YOUR_USERNAME or not YOUR_ID:
    print("🚨 致命錯誤：環境變數 AUCTION_USERNAME 或 AUCTION_ID 未設定。請檢查 GitHub Secrets。")
    # 在非 Actions 環境下，可能需要加載 .env 來測試，但這裡保持乾淨版本
    # exit(1) # 在實際部署時建議啟用，但在測試階段先註解

# ----------------- Cloudflare Checkbox 處理邏輯 -----------------

def handle_cloudflare_challenge(driver):
    """
    偵測並嘗試點擊 Cloudflare 的 "驗證您是人類" Checkbox。
    """
    CHECKBOX_LOCATOR = (By.CSS_SELECTOR, "label.cb-lb input[type='checkbox']")
    CHECKBOX_LABEL_LOCATOR = (By.CLASS_NAME, "cb-lb") # 有時點擊 Label 更有效

    print(f"[{time.strftime('%H:%M:%S')}] 🔍 正在檢查是否有 Cloudflare Checkbox 挑戰...")
    
    try:
        # 等待 Checkbox 的 Label 元素出現
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located(CHECKBOX_LABEL_LOCATOR)
        )
        
        # 找到 Checkbox 元素
        checkbox = driver.find_element(*CHECKBOX_LOCATOR)
        
        # 點擊它
        if checkbox.is_displayed() and checkbox.is_enabled():
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ 偵測到 Checkbox，正在嘗試點擊...")
            checkbox.click()
            time.sleep(5) 
            print(f"[{time.strftime('%H:%M:%S')}] ✅ Checkbox 點擊完成，等待頁面繼續載入...")
            return True
            
    except TimeoutException:
        print(f"[{time.strftime('%H:%M:%S')}] ℹ️ 沒有偵測到 Cloudflare Checkbox 挑戰 (Timeout)。繼續執行。")
        return False
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] ❌ 點擊 Checkbox 挑戰失敗: {e}")
        return False


# ----------------- 核心等待邏輯 -----------------
def element_has_non_empty_value(locator):
    """自定義 EC 條件：等待元素的 'value' 屬性變為非空 (用於 Turnstile Token)。"""
    def _predicate(driver):
        try:
            element = driver.find_element(*locator)
            element_value = element.get_attribute("value")
            return element_value is not None and element_value != ""
        except NoSuchElementException:
            return False
    return _predicate


# ----------------- 核心登入邏輯-----------------
def perform_login(driver):
    """處理 Colorbox 彈出的 Iframe 登入視窗，並執行登入。"""
    CLASS_NAME = "cboxIframe" 
    TURNSTILE_LOCATOR = (By.NAME, "cf-turnstile-response")

    # 如果環境變數為空，直接跳過登入
    if not YOUR_USERNAME or not YOUR_ID:
        print(f"[{time.strftime('%H:%M:%S')}] ❌ 環境變數缺失，無法執行登入。")
        return False

    try:
        # 1. 等待 Iframe 出現並切換
        print(f"[{time.strftime('%H:%M:%S')}] 🔍 正在等待 Colorbox Iframe 出現...")
        WebDriverWait(driver, 20).until(
            EC.frame_to_be_available_and_switch_to_it((By.CLASS_NAME, CLASS_NAME))
        )
        print(f"[{time.strftime('%H:%M:%S')}] ✅ 成功切換到登入 Iframe！")

        # 2. 等待 Turnstile 驗證完成
        print(f"[{time.strftime('%H:%M:%S')}] ⏳ 等待 Cloudflare Turnstile 完成驗證...")
        WebDriverWait(driver, 30).until( 
            element_has_non_empty_value(TURNSTILE_LOCATOR)
        )
        recaptcha_code = driver.find_element(*TURNSTILE_LOCATOR).get_attribute("value")
        print(f"[{time.strftime('%H:%M:%S')}] ✅ Turnstile 驗證成功！Token 已獲取: {recaptcha_code[:10]}...")

        # 3. 填寫帳號密碼並點擊登入
        print(f"[{time.strftime('%H:%M:%S')}] 🔍 正在定位並填寫登入資訊...")
        acc_field = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "acc")))
        acc_field.send_keys(YOUR_USERNAME)
        id_field = driver.find_element(By.ID, "id")
        id_field.send_keys(YOUR_ID)
        login_button = driver.find_element(By.ID, "loginBtn")
        
        # 4. 點擊登入
        print(f"[{time.strftime('%H:%M:%S')}] ✅ 登入按鈕點擊完成，等待回應...")
        login_button.click()
        
        # 5. 等待 Iframe 消失並切換回主框架
        WebDriverWait(driver, 5).until(EC.invisibility_of_element_located((By.CLASS_NAME, CLASS_NAME)))
        driver.switch_to.default_content()

        time.sleep(2)
        print(f"[{time.strftime('%H:%M:%S')}] 🎉 登入成功！")
        return True

    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] ⚠️ 登入操作失敗！")
        try:
            driver.switch_to.default_content()
            driver.get_screenshot_as_file("login_fail_screenshot.png")
            print(f"[{time.strftime('%H:%M:%S')}] 已保存截圖：login_fail_screenshot.png")
        except:
            pass
        print(f"[{time.strftime('%H:%M:%S')}] 🚨 登入操作失敗，錯誤訊息: {e}")
        return False
    finally:
        try:
            driver.switch_to.default_content()
        except:
            pass
            

# ----------------- 核心解析與搜尋邏輯-----------------

def parse_shop_results(driver, keyword) -> list:
    """從查詢結果表格中解析當前頁面的資料，並進行嚴格過濾 (item_name == keyword)。"""
    items_list = []
    try:
        results_tbody = driver.find_element(By.ID, "_tbody")
        rows = results_tbody.find_elements(By.TAG_NAME, "tr")
        
        if not rows:
            return items_list 
        
        for row in rows:
            try:
                shop_name = row.find_element(By.CLASS_NAME, "shopName").text.strip()
                item_name = row.find_element(By.CLASS_NAME, "itemName").text.strip()
                slot = row.find_element(By.CLASS_NAME, "slot").text.strip()
                price_raw = row.find_element(By.CSS_SELECTOR, ".price > span").text.strip().replace(',', '')
                price = int(price_raw)
                quantity_raw = row.find_element(By.CLASS_NAME, "quantity").text.strip()
                quantity = int(quantity_raw)
                trade_type = row.find_element(By.CSS_SELECTOR, ".buySell > span").text.strip()
                
                # 嚴格過濾邏輯：item_name 必須與搜尋關鍵字完全相符
                if item_name == keyword:
                    item_data = {
                        'shop_name': shop_name, 
                        'item_name': item_name, 
                        'slot': slot if slot != '-' else '',
                        'price': price, 
                        'quantity': quantity, 
                        'trade_type': trade_type,
                    }
                    items_list.append(item_data)
                
            except Exception:
                # 解析單行數據時發生錯誤，跳過該行
                continue
                
        return items_list
        
    except (NoSuchElementException, Exception):
        # 找不到表格或其它異常，返回空列表
        return items_list

def perform_search_and_get_page_count(driver, item_keyword: str) -> tuple[list, int]:
    """執行搜尋步驟並返回第一頁資料與總頁數。"""
    SERVER_NAME = "西格倫"
    SEARCH_BUTTON_ID = "a_searchBtn" 
    SERVER_XPATH = "//ol[@class='select__ol']/li[text()='西格倫']"
    
    try:
        # 1. 確保伺服器選擇器穩定
        WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.ID, "div_svr")))
        time.sleep(0.5)
        
        # 2. 嘗試關閉 SweetAlert2 彈窗
        SWEETALERT_OK_BUTTON = (By.CLASS_NAME, "swal2-confirm")
        try:
            ok_button = WebDriverWait(driver, 1).until(EC.element_to_be_clickable(SWEETALERT_OK_BUTTON))
            ok_button.click()
            print(f"[{time.strftime('%H:%M:%S')}] - ⚠️ 偵測到彈窗並關閉。")
            time.sleep(0.5)
        except TimeoutException:
            pass

        # 3. 選擇伺服器
        server_display = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "div_svr")))
        server_display.click()
        time.sleep(0.5) 
        server_option = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, SERVER_XPATH)))
        server_option.click()
        print(f"[{time.strftime('%H:%M:%S')}] - ✅ 成功選擇伺服器：【{SERVER_NAME}】")
        time.sleep(0.5) 
        
        # 4. 輸入道具關鍵字
        keyword_input = driver.find_element(By.ID, "txb_KeyWord")
        keyword_input.clear()
        keyword_input.send_keys(item_keyword)
        
        # 5. 點擊查詢並等待結果
        search_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, SEARCH_BUTTON_ID)))
        search_button.click()
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, "_tbody")))
        print(f"[{time.strftime('%H:%M:%S')}] - 🔍 查詢結果表格區塊已顯示。")

        # 6. 解析第一頁資料與獲取總頁數
        first_page_data = parse_shop_results(driver, item_keyword)
        pagination_ul = driver.find_element(By.CLASS_NAME, "pagination")
        page_links = pagination_ul.find_elements(By.XPATH, ".//li/a[contains(@onclick, 'goPage')]")
        
        max_page = 0
        for link in page_links:
            try:
                match = re.search(r'goPage\((\d+)\)', link.get_attribute('onclick'))
                if match:
                    page_num = int(match.group(1))
                    if page_num > 0:
                        max_page = max(max_page, page_num)
            except:
                continue
        
        print(f"[{time.strftime('%H:%M:%S')}] - ℹ️ 偵測到總頁數: {max_page}")
        return first_page_data, max_page
        
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] - ❌ 查詢或獲取頁數失敗: {e}")
        return [], 0


def scrape_multiple_pages(driver, max_page: int, initial_data: list, item_keyword: str) -> list:
    """處理多頁爬取邏輯"""
    if max_page <= 1:
        return initial_data

    all_data = initial_data
    for page_num in range(2, max_page + 1):
        try:
            print(f"[{time.strftime('%H:%M:%S')}] ➡️ 關鍵字【{item_keyword}】正在爬取第 {page_num}/{max_page} 頁...")
            
            link_locator = (By.XPATH, f"//ul[@class='pagination']//a[contains(@onclick, 'goPage({page_num})')]")
            page_link = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(link_locator))
            page_link.click()
            
            WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, "_tbody")))
            time.sleep(1)

            page_data = parse_shop_results(driver, item_keyword)
            all_data.extend(page_data)
            
            print(f"[{time.strftime('%H:%M:%S')}] - ✅ 第 {page_num} 頁解析成功，新增 {len(page_data)} 筆資料。")

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] - ❌ 爬取關鍵字【{item_keyword}】第 {page_num} 頁時發生錯誤: {e}。中斷翻頁。")
            break 
            
    return all_data


# ----------------- 數據分析與儲存邏輯-----------------

def analyze_and_save_summary(all_data: list, run_timestamp: str):
    """對本次爬取的所有數據進行價格分析，並儲存彙總結果。"""
    
    file_name_prefix = run_timestamp.replace('/', '_').replace(':', '-')
    FILE_NAME = f"{file_name_prefix}_summary.csv"
    
    print(f"\n[{time.strftime('%H:%M:%S')}] 📊 正在對 {len(all_data):,} 筆記錄進行數據分析...")

    records = all_data
    for record in records:
          record['timestamp'] = run_timestamp

    df = pd.DataFrame(records)
    
    if df.empty:
        print(f"[{time.strftime('%H:%M:%S')}] - ⚠️ 篩選後無可分析數據。")
        return

    df['total_value'] = df['price'] * df['quantity']
    
    # 分組彙總 '販售' 數據
    df_sell = df[df['trade_type'] == '販售'].groupby('item_name').agg(
        sell_quantity=('quantity', 'sum'),
        sell_min_price=('price', 'min'),
        sell_max_price=('price', 'max'),
        sell_total_value=('total_value', 'sum')
    ).reset_index()
    df_sell['sell_avg_price'] = df_sell.apply(
        lambda row: round(row['sell_total_value'] / row['sell_quantity'], 2) if row['sell_quantity'] > 0 else 0.0, axis=1
    ).round(0)
    df_sell = df_sell.drop(columns=['sell_total_value'])
    
    # 分組彙總 '收購' 數據
    df_buy = df[df['trade_type'] == '收購'].groupby('item_name').agg(
        buy_quantity=('quantity', 'sum'),
        buy_min_price=('price', 'min'),
        buy_max_price=('price', 'max'),
        buy_total_value=('total_value', 'sum')
    ).reset_index()
    df_buy['buy_avg_price'] = df_buy.apply(
        lambda row: round(row['buy_total_value'] / row['buy_quantity'], 2) if row['buy_quantity'] > 0 else 0.0, axis=1
    ).round(0)
    df_buy = df_buy.drop(columns=['buy_total_value'])
    
    # 合併和重新命名
    final_summary = pd.merge(df_sell, df_buy, on='item_name', how='outer').fillna(0)
    
    final_summary = final_summary.rename(columns={
        'sell_quantity': '總數量(販賣)', 'buy_quantity': '總數量(收購)', 'sell_min_price': '販賣最低價', 
        'sell_max_price': '販賣最高價', 'sell_avg_price': '販賣加權平均價', 'buy_min_price': '收購最低價', 
        'buy_max_price': '收購最高價', 'buy_avg_price': '收購加權平均價'
    })
    
    final_summary = final_summary[[
        'item_name', '總數量(販賣)', '總數量(收購)', '販賣最低價', '販賣最高價', 
        '販賣加權平均價', '收購最低價', '收購最高價', '收購加權平均價'
    ]]
    
    # 價格欄位處理
    price_cols = ['販賣最低價', '販賣最高價', '販賣加權平均價', '收購最低價', '收購最高價', '收購加權平均價']
    for col in price_cols:
          final_summary[col] = final_summary[col].apply(lambda x: int(round(x)) if x > 0 else 0)
    
    try:
        final_summary.to_csv(FILE_NAME, index=False, encoding='utf-8') 
        print(f"[{time.strftime('%H:%M:%S')}] - ✅ 成功將 {len(final_summary)} 筆彙總記錄儲存到 **{FILE_NAME}**。")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] - ❌ 儲存彙總檔案失敗: {e}")

    print("\n--- 本次彙總結果 (僅限純淨道具) ---")
    print(final_summary.to_markdown(index=False, floatfmt=".0f"))
    print("----------------------------------\n")

# ----------------- Git 自動推送邏輯 -----------------
def auto_git_push(commit_message):
    """執行 git add, commit, pull (rebase), 和 push，將新的 CSV 數據上傳到 GitHub。"""
    
    stash_popped = False 
    
    try:
        print("\n>>> 執行 Git 自動推送 (Stash -> Add CSV -> Commit -> Pull/Rebase -> Push -> Pop)...")
        
        # 0. 檢查並暫存所有未提交/未追蹤的變更 (包含新的 CSV 文件)
        stash_result = subprocess.run(
            ['git', 'stash', 'push', '--include-untracked', '-m', 'SCRAPER_TEMP_STASH'],
            check=False,
            capture_output=True
        )
        # 檢查 stdout 來判斷是否真的有東西被 Stash
        if b'No local changes to save' not in stash_result.stdout:
            print("✅ 偵測到並成功暫存 (Stash) 工作目錄變更 (包括新 CSV)。")
            stash_popped = True
        else:
            print("ℹ️ 工作目錄乾淨。無需暫存。")
        
        # 1. 恢復暫存的變更。目的：將新生成的 CSV 文件拉出來，以便被 git add 和 commit 捕獲。
        if stash_popped:
            subprocess.run(['git', 'stash', 'apply', '--index'], check=True, capture_output=True)
            print("✅ 已恢復暫存的變更到工作區。")

        # 2. Add 所有 CSV (這是您新生成的檔案)
        subprocess.run(['git', 'add', '*.csv'], check=True, capture_output=True)
        
        # 3. Commit (只有在有變更時才執行)
        commit_result = subprocess.run(
            ['git', 'commit', '-m', commit_message], 
            check=False, 
            capture_output=True
        )
        
        if commit_result.returncode != 0 and b'nothing to commit' in commit_result.stdout:
            print("ℹ️ 無新的 CSV 變更需要提交。跳過 Pull 和 Push。")
            # 如果沒有提交，但有 Stash，我們需要清理並恢復
            if stash_popped:
                subprocess.run(['git', 'stash', 'pop', '--index'], check=True, capture_output=True)
                print("✅ 已清理暫存的變更。")
            return
            
        print("✅ 本地提交完成。")
        
        # 4. Pull (Rebase)
        print("🔍 正在拉取遠端最新變更 (git pull --rebase)...")
        # 假設您的 Actions 使用的是 GITHUB_TOKEN，預設拉取/推送 main
        subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'], check=True, capture_output=True)
        print("✅ 遠端同步完成。")
        
        # 5. Push
        subprocess.run(['git', 'push', 'origin', 'main'], check=True, capture_output=True)
        print("🎉 Git 操作成功：最新 CSV 數據已推送至 GitHub。")
        
        # 6. 清理並恢復暫存的變更（如果有的話）
        if stash_popped:
            subprocess.run(['git', 'stash', 'drop'], check=True, capture_output=True)
            print("✅ 已清理暫存的變更。")


    except subprocess.CalledProcessError as e:
        # 在失敗時，檢查並恢復原始的 Stash 變更
        if stash_popped:
            try:
                subprocess.run(['git', 'stash', 'pop', '--index'], check=False, capture_output=True)
                print("⚠️ Git 操作失敗，但已嘗試恢復暫存的變更。")
            except:
                pass
                
        print(f"❌ Git 操作失敗，請檢查您的 Git 環境或認證：")
        # 打印錯誤輸出，方便調試
        # print(f"STDOUT:\n{e.stdout.decode()}")
        # print(f"STDERR:\n{e.stderr.decode()}")
    except FileNotFoundError:
        print("❌ 找不到 Git 命令。請確保您的系統已安裝 Git。")

# ----------------- 單次排程任務核心邏輯 -----------------
def run_scraping_task(driver, SEARCH_ITEMS, run_timestamp_for_file):
    """執行所有關鍵字的爬蟲和數據處理。"""
    
    print("\n" + "="*80)
    print(" " * 28 + "【爬蟲任務開始】")
    print(f" " * 28 + f"【排程時間戳: {run_timestamp_for_file}】")
    print("="*80)

    all_data_for_summary: list = []
    total_records = 0

    try:
        # 嘗試一個簡單操作來檢查 Driver 是否有效
        driver.find_element(By.ID, "a_searchBtn").click() 
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, "div_svr")))
        time.sleep(1)

        for item_keyword in SEARCH_ITEMS:
            print("\n" + "#"*60)
            print(f"[{time.strftime('%H:%M:%S')}] - 【開始處理關鍵字：{item_keyword.upper()}】")
            print("#"*60)
            
            initial_data, max_page = perform_search_and_get_page_count(driver, item_keyword)

            if max_page > 0:
                full_item_data = scrape_multiple_pages(driver, max_page, initial_data, item_keyword)
            else:
                full_item_data = initial_data
            
            all_data_for_summary.extend(full_item_data)
            total_records += len(full_item_data)
            print(f"[{time.strftime('%H:%M:%S')}] - ✅ 關鍵字【{item_keyword}】數據收集完畢，總共 {len(full_item_data)} 筆資料。")

        # --- 數據分析、儲存彙總 CSV 與 Git 推送 ---
        if total_records > 0:
            analyze_and_save_summary(all_data_for_summary, run_timestamp_for_file)
            
            # *** 自動 Git 推送最新 CSV ***
            timestamp_for_commit = datetime.now().strftime("%Y-%m-%d %H:%M")
            commit_msg = f"Hourly data update (CSV) via scraper: {timestamp_for_commit}"
            
            auto_git_push(commit_msg)
            # *******************************
            
        else:
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ 本次排程沒有爬取到任何記錄，跳過數據分析。")

        print(f"\n[{time.strftime('%H:%M:%S')}] ✨ **本次爬蟲總計 {total_records:,} 筆記錄。**")
        return True 

    except WebDriverException as e:
        print(f"[{time.strftime('%H:%M:%S')}] 🚨 爬蟲任務執行期間發生 WebDriver 錯誤: {e}")
        return False 

    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] 🚨 爬蟲任務執行期間發生其他錯誤: {e}")
        return True


# ----------------- 主流程-----------------

def run_hourly_monitoring_cycle(url: str):
    """
    執行一次初始化 Driver -> 登入 -> 爬蟲 -> 關閉 Driver。
    """
    SEARCH_ITEMS = ["鋁", "大嘴鳥卡片", "神之金屬"] 
    
    # ... (初始化和重試邏輯) ...
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # ... (清理舊 Driver 邏輯) ...
            
            print(f"[{time.strftime('%H:%M:%S')}] 🔄 正在初始化新的瀏覽器 Driver...")
            
            # 【重要修正】：新增無頭模式和必要的參數
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')         # 消除沙箱模式的權限問題 (Linux 必需)
            options.add_argument('--headless')           # 強制無頭模式 (避免圖形界面依賴)
            options.add_argument('--disable-dev-shm-usage') # 解決 Linux 內存問題
            options.add_argument('--disable-gpu')        # 禁用 GPU 加速
            
            # 使用修正後的 options 初始化 Driver
            driver = uc.Chrome(options=options)
            driver.get(url)
            time.sleep(3) 

            # --------------------- Cloudflare Checkbox 處理步驟 ---------------------
            handle_cloudflare_challenge(driver)
            # -------------------------------------------------------------------------

            # 點擊登入連結並執行登入 (這裡的 ID 'a_searchBtn' 似乎同時是登入連結和查詢按鈕)
            LOGIN_LINK_ID = "a_searchBtn"
            login_link = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, LOGIN_LINK_ID)))
            login_link.click()
            login_success = perform_login(driver)
            
            if login_success:
                break
                
            if attempt < MAX_RETRIES:
                print(f"[{time.strftime('%H:%M:%S')}] 😥 第 {attempt} 次初始化/登入失敗，正在重試...")
            
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] ❌ 瀏覽器或登入初始化失敗: {e}")
            if attempt < MAX_RETRIES:
                 print(f"[{time.strftime('%H:%M:%S')}] 😥 第 {attempt} 次初始化/登入失敗，正在重試...")


    if login_success and driver:
        # 3. 執行任務
        now = datetime.now()
        # 注意：這裡的strftime格式需要根據您實際的系統/環境來調整，以確保與您原來的效果一致
        # '%#m' 和 '%#d' 在某些系統 (如 Linux/GitHub Actions) 上可能無法工作，但這裡保持原樣
        run_timestamp_for_file = now.strftime('%Y/%m/%d/%H') 
        run_scraping_task(driver, SEARCH_ITEMS, run_timestamp_for_file) 
    else:
        print(f"[{time.strftime('%H:%M:%S')}] 😥 登入失敗，跳過本次爬蟲任務。")

    # 4. 關閉 Driver
    if driver:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧹 任務結束，正在關閉瀏覽器 Driver...")
        try:
            driver.quit() 
        except Exception:
            pass
    

# --- 執行程式碼 (單次執行) ---
if __name__ == '__main__':
    target_url = "https://event.gnjoy.com.tw/RoZ/RoZ_ShopSearch" 
    print("==============================================")
    print("      🎉 爬蟲測試程式已啟動 (單次執行) 🎉")
    print("==============================================")
    # 執行一次任務
    run_hourly_monitoring_cycle(target_url) 
    print("==============================================")
    print("           ✨ 任務執行完畢，程式結束。 ✨")
    print("==============================================")