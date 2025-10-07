# 檔案: main.py (包含最終優化的 Iframe Checkbox 處理)
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
# 【新增】：匯入圖像識別模組
import image_click_handler
from selenium.webdriver.common.action_chains import ActionChains # 用於模擬滑鼠移動和點擊
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


# ----------------- 環境變數 (請替換為您的實際帳號密碼) -----------------

# 這些變數會直接從 GitHub Actions 的 'env:' 區塊或系統環境變數中讀取
# 建議使用 os.getenv 確保安全性，但在本範例中先直接寫入供測試
YOUR_USERNAME = os.environ.get("AUCTION_USERNAME", "nyto1201")
YOUR_ID = os.environ.get("AUCTION_ID", "N225116709") 

MAX_RETRIES = 3 

if not YOUR_USERNAME or not YOUR_ID:
    print("🚨 致命錯誤：環境變數 AUCTION_USERNAME 或 AUCTION_ID 未設定。請檢查 GitHub Secrets。")
    # exit(1) # 實際部署時建議啟用

# ----------------- 偵錯輔助函數 -----------------

def check_and_save_screenshot(driver, stage_name: str, success: bool = True):
    """
    自定義截圖函數，用於記錄特定階段的結果。
    """
    status = "SUCCESS" if success else "FAIL"
    filename = f"screenshot_{stage_name}_{status}_{datetime.now().strftime('%H%M%S')}.png"
    try:
        driver.get_screenshot_as_file(filename)
        print(f"[{time.strftime('%H:%M:%S')}] 📸 已保存截圖：{filename}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] ❌ 截圖失敗: {e}")

# ----------------- Cloudflare 驗證輔助函數 -----------------

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

# ----------------- 核心登入邏輯 (採用 OpenCV 圖像識別點擊) -----------------
def perform_login(driver):
    time.sleep(5)
    """
    處理 Colorbox 彈出的 Iframe 登入視窗，並執行登入。
    【強化點】：使用 OpenCV 圖像識別定位 Checkbox 並點擊。
    """
    CLASS_NAME = "cboxIframe" 
    TURNSTILE_LOCATOR = (By.NAME, "cf-turnstile-response") # Turnstile Token 欄位

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

        # --------------------- 【重要】OpenCV 圖像識別點擊 ---------------------
        print(f"[{time.strftime('%H:%M:%S')}] ⏳ 嘗試使用 OpenCV 定位 Checkbox...")
        
        # 獲取 Iframe 內 Checkbox 的中心座標 (x, y)
        click_coords = image_click_handler.locate_checkbox_and_get_center_coords(driver)
        
        if click_coords:
            center_x, center_y = click_coords
            
            # 1. 嘗試使用 ActionChains 點擊座標
            try:
                actions = ActionChains(driver)
                # 移動到目標座標 (相對於 Iframe 視口)
                actions.move_by_offset(center_x, center_y).click().perform()
                print(f"[{time.strftime('%H:%M:%S')}] ✅ 圖像識別定位點 ({center_x}, {center_y}) 並使用 ActionChains 點擊完成！")
                
                # 清理 ActionChains 累積的座標位移
                actions.reset_actions() 
                
            except Exception as e:
                # 如果 ActionChains 失敗，嘗試使用 JS 強制點擊座標
                print(f"[{time.strftime('%H:%M:%S')}] ❌ ActionChains 點擊失敗: {e}。嘗試 JS 點擊...")
                # 這是 Iframe 內最暴力的點擊方式
                driver.execute_script(f"document.elementFromPoint({center_x}, {center_y}).click();")
                print(f"[{time.strftime('%H:%M:%S')}] ✅ JS 強制點擊座標完成！")
            
            time.sleep(5) # 給予驗證反應時間
            
        else:
            print(f"[{time.strftime('%H:%M:%S')}] ℹ️ 圖像識別未找到 Checkbox，假設是自動 Turnstile 或等待 Token。")
        # -----------------------------------------------------------------------------------------

        # 2. 等待 Turnstile 驗證完成 (最終 Token 必須出現)
        print(f"[{time.strftime('%H:%M:%S')}] ⏳ 等待 Cloudflare Turnstile Token 生成...")
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
            # 確保切換回主框架並拍照
            driver.switch_to.default_content() 
            check_and_save_screenshot(driver, "Login_Iframe_Fail", success=False)
        except:
            pass
        print(f"[{time.strftime('%H:%M:%S')}] 🚨 登入操作失敗，錯誤訊息: {e}")
        return False
    finally:
        try:
            # 確保最後切回主框架
            driver.switch_to.default_content()
        except:
            pass
            
# ----------------- 核心解析與搜尋邏輯 (與先前版本一致) -----------------

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
        
        # 2. 嘗試關閉 SweetAlert2 彈窗 (如果出現)
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


# ----------------- 數據分析與儲存邏輯 (與先前版本一致) -----------------
def analyze_and_save_summary(all_data: list, run_timestamp: str):
    """對本次爬取的所有數據進行價格分析，並儲存彙總結果。"""
    
    data_dir = 'data'
    # 1. 確保 data 目錄存在 (與主數據儲存邏輯一致)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    file_name_prefix = run_timestamp.replace('/', '_').replace(':', '-')
    FILE_NAME = f"{file_name_prefix}_summary.csv"
    # 2. 修正：將彙總檔案路徑指向 data/
    FILE_PATH = os.path.join(data_dir, FILE_NAME) 
    
    print(f"\n[{time.strftime('%H:%M:%S')}] 📊 正在對 {len(all_data):,} 筆記錄進行數據分析...")

    records = all_data
    for record in records:
          record['timestamp'] = run_timestamp

    df = pd.DataFrame(records)
    
    if df.empty:
        print(f"[{time.strftime('%H:%M:%M')}] - ⚠️ 篩選後無可分析數據。")
        return "" # 返回空字串以避免錯誤

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
        final_summary.to_csv(FILE_PATH, index=False, encoding='utf-8') 
        print(f"[{time.strftime('%H:%M:%S')}] - ✅ 成功將 {len(final_summary)} 筆彙總記錄儲存到 **{FILE_PATH}**。")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] - ❌ 儲存彙總檔案失敗: {e}")

    print("\n--- 本次彙總結果 (僅限純淨道具) ---")
    print(final_summary.to_markdown(index=False, floatfmt=".0f"))
    print("----------------------------------\n")
    
    return f"本次爬蟲總計 {len(records)} 筆記錄。"

def auto_git_push(commit_message):
    """執行 Git 操作來推送新的 CSV 文件 (已精簡)"""
    print(f"[{time.strftime('%H:%M:%S')}] >>> 執行 Git 自動推送 (Add -> Commit -> Pull Rebase -> Push)...")
    
    # Git 操作列表，成功時返回 True
    def run_git_command(command, error_msg):
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            if command[1] == 'pull' and "Fast-forward" not in result.stdout and "Already up to date" not in result.stdout:
                # 如果 Pull Rebase 成功，但有實際合併內容時的提示
                print(f"[{time.strftime('%H:%M:%S')}] ℹ️ Git Pull Rebase 成功，合併了遠端變更。")
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ {error_msg} 失敗。")
            print(f"[{time.strftime('%H:%M:%S')}] 錯誤輸出: {e.stderr.strip()}")
            return False, e.stderr
        except FileNotFoundError:
            print(f"[{time.strftime('%H:%M:%S')}] ❌ Git 指令未找到。請確保 Git 已安裝並在 PATH 中。")
            return False, "Git command not found"

    commit_success = False

    # 1. Add all changes: Use 'git add -A' to stage all modified, deleted, and new files (包括 data/ 和可能的診斷文件).
    # 修正：確保所有已修改或新建立的文件都被加入暫存區，以清理工作目錄。
    if not run_git_command(['git', 'add', '-A'], "Add 所有變更 (包括 data/ 和可能的診斷文件)")[0]:
        return False
        
    # 2. Commit
    # 執行提交並檢查輸出結果，以判斷是否有實際變更被提交
    commit_result = subprocess.run(['git', 'commit', '-m', commit_message], capture_output=True, text=True)
    
    if commit_result.returncode == 0:
        print(f"[{time.strftime('%H:%M:%S')}] ✅ 本地提交完成。")
        commit_success = True
    elif "nothing to commit" in commit_result.stdout:
        print(f"[{time.strftime('%H:%M:%S')}] ℹ️ 本次沒有新的數據變更需要提交。")
        commit_success = False # 雖然沒有提交，但我們仍需要 Pull 來更新 Plot
    else:
        print(f"[{time.strftime('%H:%M:%S')}] ⚠️ 本地提交失敗。")
        print(f"[{time.strftime('%H:%M:%S')}] 錯誤輸出: {commit_result.stderr.strip()}")
        return False
        
    # 3. Pull/Rebase 遠端變更 (始終執行，以拉取 Plot 檔案)
    # 現在工作目錄應該是乾淨的，Pull Rebase 不會被 unstaged changes 阻擋。
    print(f"[{time.strftime('%H:%M:%S')}] 🔍 正在拉取遠端最新變更 (git pull --rebase origin main)...")
    if not run_git_command(['git', 'pull', '--rebase', 'origin', 'main'], "Git Pull Rebase")[0]:
        # 如果 Rebase 失敗，通常是權限或衝突。
        print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Git Pull Rebase 失敗，請檢查 Git 認證或是否有衝突需要解決。")
        return False

    # 4. Push 變更 (如果成功提交，或者 Pull 動作本身導致了 Rebase)
    if commit_success:
        if not run_git_command(['git', 'push', 'origin', 'main'], "Git Push")[0]:
            print(f"[{time.strftime('%H:%M:%S')}] ❌ Git Push 失敗。請檢查遠端狀態。")
            return False
        print(f"[{time.strftime('%H:%M:%S')}] 🎉 Git Push 成功完成。")
        
    elif not commit_success:
        print(f"[{time.strftime('%H:%M:%S')}] ℹ️ 無新數據提交，Pull 已完成遠端 Plot 更新。Push 步驟跳過。")
    
    return True

# ----------------- 單次排程任務核心邏輯 (與先前版本一致) -----------------
def run_scraping_task(driver, SEARCH_ITEMS, run_timestamp_for_file):
    """執行所有關鍵字的爬蟲和數據處理。"""
    
    print("\n" + "="*80)
    print(" " * 28 + "【爬蟲任務開始】")
    print(" " * 28 + f"【排程時間戳: {run_timestamp_for_file}】")
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
            
            timestamp_for_commit = datetime.now().strftime("%Y-%m-%d %H:%M")
            commit_msg = f"Hourly data update (CSV) via scraper: {timestamp_for_commit}"
            
            auto_git_push(commit_msg)
            
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


# ----------------- 主流程 (含 Driver 初始化優化和 Cloudflare 檢查) -----------------

def check_main_cloudflare(driver) -> bool:
    """
    檢查主頁面是否卡在 Cloudflare 驗證。
    如果偵測到 Turnstile Iframe，則等待 20 秒讓其自動通過。
    """
    TURNSTILE_IFRAME_LOCATOR = (By.CSS_SELECTOR, 'iframe[src*="cloudflare"]')
    
    try:
        # 等待 Turnstile Iframe 出現 (給予 5 秒確認時間)
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located(TURNSTILE_IFRAME_LOCATOR)
        )
        print(f"[{time.strftime('%H:%M:%S')}] 🚨 偵測到 Cloudflare Turnstile 主頁面驗證！")
        check_and_save_screenshot(driver, "Main_CF_Start", success=False)
        
        # 切換到 Iframe 等待 Token 出現 (通常會自動完成)
        WebDriverWait(driver, 20).until(
            EC.frame_to_be_available_and_switch_to_it(TURNSTILE_IFRAME_LOCATOR)
        )
        
        # 這是 Turnstile Iframe 內的 Token 欄位
        TURNSTILE_RESPONSE_LOCATOR = (By.NAME, "cf-turnstile-response") 
        WebDriverWait(driver, 10).until(
            element_has_non_empty_value(TURNSTILE_RESPONSE_LOCATOR)
        )
        
        driver.switch_to.default_content()
        print(f"[{time.strftime('%H:%M:%S')}] ✅ Cloudflare Turnstile 自動驗證通過。")
        check_and_save_screenshot(driver, "Main_CF_Success", success=True)
        return True # 表示驗證已完成
        
    except TimeoutException:
        # 如果 5 秒內沒有偵測到 Iframe，或者 20 秒內沒有通過驗證
        driver.switch_to.default_content() # 確保切回主框架
        current_title = driver.title
        
        if "Just a moment" in current_title or "Cloudflare" in current_title:
             print(f"[{time.strftime('%H:%M:%S')}] ❌ 主頁面驗證失敗或超時，標題: {current_title[:30]}...")
             check_and_save_screenshot(driver, "Main_CF_Failure", success=False)
             return False # 主頁面驗證失敗
        else:
             print(f"[{time.strftime('%H:%M:%S')}] ℹ️ 主頁面未發現 Cloudflare 驗證，繼續下一步。")
             return True # 頁面似乎是正常的，繼續

def run_hourly_monitoring_cycle(url: str):
    """
    執行一次初始化 Driver -> 登入 -> 爬蟲 -> 關閉 Driver。
    """
    SEARCH_ITEMS = ["大嘴鳥卡片"] 
    
    login_success = False 
    driver = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # 清理舊 Driver 邏輯
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = None

            print(f"[{time.strftime('%H:%M:%S')}] 🔄 正在初始化新的瀏覽器 Driver (第 {attempt}/{MAX_RETRIES} 次重試)...")
            
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage') 
            options.add_argument('--disable-gpu')
            
            # 【關鍵優化】：強制設定無頭模式的視窗大小
            options.add_argument('--window-size=1920,1080') 
            
            # 💡 部署時請將 `headless=False` 改為 `headless=True`
            driver = uc.Chrome(options=options, headless=False, use_subprocess=True) 
            driver.get(url)
            time.sleep(1) # 縮短延遲，讓 Check 函數立即執行

            # --------------------- Cloudflare 主頁面檢查 ---------------------
            if not check_main_cloudflare(driver):
                 # 如果主頁面驗證失敗，則中斷本次嘗試並重試
                 continue 
            # ------------------------------------------------------------------

            # 點擊登入連結並執行登入 (這裡會觸發 Iframe 彈出)
            LOGIN_LINK_ID = "a_searchBtn"
            # 必須等待登入按鈕出現 (表示主頁面載入成功)
            login_link = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, LOGIN_LINK_ID)))
            login_link.click()
            login_success = perform_login(driver) # 進入 perform_login 處理 Iframe 內的驗證
            
            if login_success:
                check_and_save_screenshot(driver, "Login_Main_Page_Success", success=True)
                break
                
            if attempt < MAX_RETRIES:
                print(f"[{time.strftime('%H:%M:%S')}] 😥 第 {attempt} 次初始化/登入失敗，正在重試...")
            
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] ❌ 瀏覽器或登入初始化失敗: {e}")
            check_and_save_screenshot(driver, "General_Init_Fail", success=False)
            if attempt < MAX_RETRIES:
                print(f"[{time.strftime('%H:%M:%S')}] 😥 第 {attempt} 次初始化/登入失敗，正在重試...")
            continue


    if login_success and driver:
        # 3. 執行任務
        now = datetime.now()
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
    print("           🎉 爬蟲測試程式已啟動 (單次執行) 🎉")
    print("==============================================")
    # 執行一次任務
    run_hourly_monitoring_cycle(target_url) 
    print("==============================================")
    print("             ✨ 任務執行完畢，程式結束。 ✨")
    print("==============================================")