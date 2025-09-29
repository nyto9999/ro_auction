# 檔案: main_scraper.py (已修正 save_to_csv_and_update_history 函式為 analyze_and_save_summary)
from datetime import datetime
import os
# ... (省略其他匯入和 Class AuctionItem 的定義，假設它們與您提供的原始碼一致)
import undetected_chromedriver as uc
import time
import json 
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException 
import pandas as pd
import re
from selenium.common.exceptions import WebDriverException

# 假設 model/auction_item.py 已經存在
# 為了讓此腳本獨立運行，我們假設 AuctionItem 類別的定義
class AuctionItem:
    def __init__(self, shop_name, item_name, slot, price, quantity, trade_type):
        self.shop_name = shop_name
        self.item_name = item_name
        self.slot = slot
        self.price = price
        self.quantity = quantity
        self.trade_type = trade_type
    
    def __dict__(self):
        return {
            "shop_name": self.shop_name,
            "item_name": self.item_name,
            "slot": self.slot,
            "price": self.price,
            "quantity": self.quantity,
            "trade_type": self.trade_type
        }

# 替換成你的實際帳號和密碼
YOUR_USERNAME = "nyto1201" # 請替換
YOUR_ID = "N225116709" # 請替換

# ----------------- 核心等待邏輯 (自定義函式) -----------------
def element_has_non_empty_value(locator):
    # ... (此處保留原始碼)
    """自定義 EC 條件：等待元素的 'value' 屬性變為非空且長度大於 10 (用於 Turnstile Token)。"""
    def _predicate(driver):
        try:
            element = driver.find_element(*locator)
            element_value = element.get_attribute("value")
            # 簡化長度判斷，只要非空即可
            return element_value is not None and element_value != ""
        except NoSuchElementException:
            return False
    return _predicate
# ----------------- 核心登入邏輯 -----------------
def perform_login(driver):
    # ... (此處保留原始碼)
    """
    處理 Colorbox 彈出的 Iframe 登入視窗，並執行登入。
    """
    CLASS_NAME = "cboxIframe" 
    TURNSTILE_LOCATOR = (By.NAME, "cf-turnstile-response")

    try:
        # 1. 等待 Iframe 出現並切換
        print(f"[{time.strftime('%H:%M:%S')}] 🔍 正在等待 Colorbox Iframe (Class: {CLASS_NAME}) 出現...")
        WebDriverWait(driver, 20).until(
            EC.frame_to_be_available_and_switch_to_it((By.CLASS_NAME, CLASS_NAME))
        )
        print(f"[{time.strftime('%H:%M:%S')}]   ✅ 成功切換到登入 Iframe！")

        # 2. 等待 Turnstile 驗證完成
        print(f"[{time.strftime('%H:%M:%S')}] ⏳ 等待 Cloudflare Turnstile 完成驗證...")
        # 將等待時間延長到 30 秒，給予充足時間讓 Turnstile 通過
        WebDriverWait(driver, 30).until( 
            element_has_non_empty_value(TURNSTILE_LOCATOR)
        )
        recaptcha_code = driver.find_element(*TURNSTILE_LOCATOR).get_attribute("value")
        print(f"[{time.strftime('%H:%M:%S')}]   ✅ Turnstile 驗證成功！Token 已獲取: {recaptcha_code[:10]}...")

        # 3. 填寫帳號密碼並點擊登入
        print(f"[{time.strftime('%H:%M:%S')}] 🔍 正在定位並填寫登入資訊...")
        acc_field = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "acc")))
        acc_field.send_keys(YOUR_USERNAME)
        id_field = driver.find_element(By.ID, "id")
        id_field.send_keys(YOUR_ID)
        login_button = driver.find_element(By.ID, "loginBtn")
        
        # 4. 點擊登入
        print(f"[{time.strftime('%H:%M:%S')}]   ✅ 登入按鈕點擊完成，等待回應...")
        login_button.click()
        
        # 5. 等待 Iframe 消失並切換回主框架
        WebDriverWait(driver, 5).until(EC.invisibility_of_element_located((By.CLASS_NAME, CLASS_NAME)))
        driver.switch_to.default_content()

        # 等待登入成功後的頁面載入（例如登入狀態改變）
        time.sleep(2)

        print(f"[{time.strftime('%H:%M:%S')}] 🎉 登入成功！")
        return True

    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] ⚠️ 登入操作失敗！")
        # 確保回到主框架並截圖
        try:
            driver.switch_to.default_content()
            driver.get_screenshot_as_file("login_fail_screenshot.png")
            print(f"[{time.strftime('%H:%M:%S')}]   已保存截圖：login_fail_screenshot.png")
        except:
            pass
        print(f"[{time.strftime('%H:%M:%S')}] 🚨 登入操作失敗，錯誤訊息: {e}")
        return False
    finally:
        # 確保在結束時切換到主框架
        try:
            driver.switch_to.default_content()
        except:
            pass
            
# ----------------- 核心解析邏輯 -----------------
def parse_shop_results(driver) -> list[AuctionItem]:
    # ... (此處保留原始碼)
    """從查詢結果表格中解析當前頁面的所有露天商店道具資料。"""
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
                
                price_element = row.find_element(By.CSS_SELECTOR, ".price > span")
                price_raw = price_element.text.strip().replace(',', '')
                price = int(price_raw)
                
                quantity_raw = row.find_element(By.CLASS_NAME, "quantity").text.strip()
                quantity = int(quantity_raw)
                
                trade_type = row.find_element(By.CSS_SELECTOR, ".buySell > span").text.strip()
                
                item = AuctionItem(
                    shop_name=shop_name,
                    item_name=item_name,
                    slot=slot if slot != '-' else '',
                    price=price,
                    quantity=quantity,
                    trade_type=trade_type
                )
                items_list.append(item)
                
            except Exception:
                continue
                
        return items_list

    except (NoSuchElementException, Exception):
        return items_list
    
# ----------------- 核心搜尋與分頁邏輯 -----------------
def perform_search_and_get_page_count(driver, item_keyword: str) -> tuple[list[AuctionItem], int]:
    # ... (省略步驟 0 Turnstile 驗證)

    # --- 1. 常數定義 ---
    SERVER_NAME = "西格倫"
    SEARCH_BUTTON_ID = "a_searchBtn" 
    SERVER_XPATH = "//ol[@class='select__ol']/li[text()='西格倫']"
    
    # --- 修正：新增穩定性等待 ---
    try:
        WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.ID, "div_svr")))
        time.sleep(1.5) 
        print(f"[{time.strftime('%H:%M:%S')}]  - ✅ 伺服器選擇器載入穩定。")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}]  - ❌ 等待伺服器選擇器穩定失敗: {e}")
        return [], 0
        
    # --- 新增步驟 1.5: 檢查並關閉 SweetAlert2 彈窗 (例如: 「請點選伺服器」) ---
    SWEETALERT_OK_BUTTON = (By.CLASS_NAME, "swal2-confirm")
    try:
        # 使用極短的等待時間 (1秒)，如果彈窗存在就點擊
        ok_button = WebDriverWait(driver, 1).until(
            EC.element_to_be_clickable(SWEETALERT_OK_BUTTON)
        )
        ok_button.click()
        print(f"[{time.strftime('%H:%M:%S')}]  - ⚠️ 偵測到 SweetAlert2 彈窗並成功點擊 OK 關閉。")
        time.sleep(1) # 等待彈窗關閉
    except TimeoutException:
        # 如果 1 秒內沒有找到按鈕，表示彈窗沒出現，這是正常的
        print(f"[{time.strftime('%H:%M:%S')}]  - ✅ 未偵測到 SweetAlert2 彈窗，繼續。")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}]  - ❌ 關閉 SweetAlert2 彈窗時發生錯誤: {e}")
        # 即使失敗，也嘗試繼續執行，因為它可能不影響後續操作

    # --- 2. 選擇伺服器：西格倫 (這部分保持不變) ---
    try:
        # 2a. 點擊伺服器顯示框，讓選項列表出現
        server_display = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "div_svr")))
        server_display.click()
        time.sleep(0.5) 
        
        # 2b. 點擊實際的伺服器選項
        server_option = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, SERVER_XPATH)))
        server_option.click()
        print(f"[{time.strftime('%H:%M:%S')}]  - ✅ 成功選擇伺服器：【{SERVER_NAME}】")
        time.sleep(0.5) 
        
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}]  - ❌ 選擇伺服器失敗: {e}")
        return [], 0
    # --- 3. 輸入道具關鍵字 ---
    try:
        keyword_input = driver.find_element(By.ID, "txb_KeyWord")
        keyword_input.clear()
        keyword_input.send_keys(item_keyword)
        print(f"[{time.strftime('%H:%M:%S')}]  - ✅ 成功輸入道具關鍵字：【{item_keyword}】")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}]  - ❌ 輸入道具關鍵字失敗: {e}")
        return [], 0
        
    # --- 4. 點擊查詢按鈕並等待結果表格 ---
    try:
        search_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, SEARCH_BUTTON_ID)))
        search_button.click()
        print(f"[{time.strftime('%H:%M:%S')}]  - ✅ 成功點擊【查詢】按鈕。")
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, "_tbody")))
        print(f"[{time.strftime('%H:%M:%S')}]  - 🔍 查詢結果表格區塊已顯示。")

        # --- 5. 解析第一頁資料與獲取總頁數 ---
        first_page_data = parse_shop_results(driver)
        
        pagination_ul = driver.find_element(By.CLASS_NAME, "pagination")
        page_links = pagination_ul.find_elements(By.XPATH, ".//li/a[contains(@onclick, 'goPage')]")
        
        max_page = 0
        for link in page_links:
            try:
                # 這裡尋找最大的頁碼數字
                match = re.search(r'goPage\((\d+)\)', link.get_attribute('onclick'))
                if match:
                    page_num = int(match.group(1))
                    if page_num > 0:
                        max_page = max(max_page, page_num)
            except:
                continue
        
        print(f"[{time.strftime('%H:%M:%S')}]  - ℹ️ 偵測到總頁數: {max_page}")
        return first_page_data, max_page
        
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}]  - ❌ 查詢或獲取頁數失敗: {e}")
        return [], 0

def scrape_multiple_pages(driver, max_page: int, initial_data: list[AuctionItem], item_keyword: str) -> list[AuctionItem]:
    # ... (此處保留原始碼)
    """處理多頁爬取邏輯。"""
    if max_page <= 1:
        print(f"[{time.strftime('%H:%M:%S')}]  - 🛑 關鍵字【{item_keyword}】只有 1 頁或更少，無需翻頁。")
        return initial_data

    all_data = initial_data
    
    # 從第 2 頁開始遍歷到最大頁數
    for page_num in range(2, max_page + 1):
        try:
            print(f"[{time.strftime('%H:%M:%S')}] ➡️ 關鍵字【{item_keyword}】正在爬取第 {page_num}/{max_page} 頁...")
            
            # 找到並點擊對應的頁碼連結
            link_locator = (By.XPATH, f"//ul[@class='pagination']//a[contains(@onclick, 'goPage({page_num})')]")
            page_link = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(link_locator))
            page_link.click()
            
            # 等待表格內容更新
            WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, "_tbody")))
            time.sleep(1) # 給予緩衝時間

            # 解析當前頁面資料
            page_data = parse_shop_results(driver)
            all_data.extend(page_data)
            
            print(f"[{time.strftime('%H:%M:%S')}]  - ✅ 第 {page_num} 頁解析成功，新增 {len(page_data)} 筆資料。")

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}]  - ❌ 爬取關鍵字【{item_keyword}】第 {page_num} 頁時發生錯誤: {e}。中斷翻頁。")
            break 
            
    return all_data

# ----------------- 數據分析與儲存邏輯 (新功能) -----------------

def analyze_and_save_summary(all_data: list[AuctionItem], run_timestamp: str):
    """
    對本次爬取的所有數據進行價格分析，並以時間戳命名檔案儲存彙總結果。
    
    :param all_data: 本次爬取的所有道具 AuctionItem 清單。
    :param run_timestamp: 本次執行的格式化時間戳 (e.g., '2025/9/25/15')。
    """
    
    # 檔案命名格式: YYYY_M_D_H_summary.csv
    file_name_prefix = run_timestamp.replace('/', '_') 
    FILE_NAME = f"{file_name_prefix}_summary.csv"
    
    print(f"\n[{time.strftime('%H:%M:%S')}] 📊 正在對 {len(all_data):,} 筆記錄進行數據分析...")

    # 1. 轉換為 Pandas DataFrame
    records = []
    for item in all_data:
        record = item.__dict__().copy()
        record['timestamp'] = run_timestamp
        records.append(record)
    
    df = pd.DataFrame(records)
    
    # ***** 關鍵修正步驟：嚴格篩選道具名稱 (沿用上次的邏輯) *****
    initial_count = len(df)
    
    # 過濾掉那些明顯是「裝備+卡片+附魔」的複雜組合
    df_filtered = df[~df['item_name'].str.contains(r'^\+', regex=True, na=False)] # 排除以 + 開頭
    df_filtered = df_filtered[~df_filtered['item_name'].str.contains(r' MHP | DEF | STR | AGI | DEX | INT | VIT | LUK | 變動詠唱', na=False)] # 排除附魔
    df_filtered = df_filtered[df_filtered['item_name'].apply(lambda x: x.count(' ') <= 2)] # 名字最多只允許 2 個空格 (如: 大嘴鳥 卡片)
    
    # 最終篩選後的 df
    df = df_filtered.copy()
    
    print(f"[{time.strftime('%H:%M:%S')}]  - 🗑️ 已排除 {initial_count - len(df):,} 筆複雜裝備記錄，剩餘 {len(df):,} 筆純淨道具記錄進行分析。")
    # ----------------------------------------------------------------------------------
    
    if df.empty:
        print(f"[{time.strftime('%H:%M:%S')}]  - ⚠️ 篩選後無可分析數據。")
        return

    # 針對收購/販賣分別計算總量和價格
    df['total_value'] = df['price'] * df['quantity']
    
    # 建立一個輔助函式來計算加權平均價 (WAP)
    def calculate_weighted_avg(group):
        total_value = group['total_value'].sum()
        total_quantity = group['quantity'].sum()
        if total_quantity == 0:
            return 0.0
        return round(total_value / total_quantity, 2)
    
    # --- 2. 彙總【販售】數據 (trade_type == '販售') ---
    df_sell = df[df['trade_type'] == '販售'].groupby('item_name').agg(
        sell_quantity=('quantity', 'sum'),
        sell_min_price=('price', 'min'),
        sell_max_price=('price', 'max'),
        sell_total_value=('total_value', 'sum')
    ).reset_index()
    df_sell['sell_avg_price'] = df_sell.apply(
        lambda row: round(row['sell_total_value'] / row['sell_quantity'], 2) 
                    if row['sell_quantity'] > 0 else 0.0, 
        axis=1
    )
    df_sell = df_sell.drop(columns=['sell_total_value'])
    
    # --- 3. 彙總【收購】數據 (trade_type == '收購') ---
    df_buy = df[df['trade_type'] == '收購'].groupby('item_name').agg(
        buy_quantity=('quantity', 'sum'),
        buy_min_price=('price', 'min'),
        buy_max_price=('price', 'max'),
        buy_total_value=('total_value', 'sum')
    ).reset_index()
    df_buy['buy_avg_price'] = df_buy.apply(
        lambda row: round(row['buy_total_value'] / row['buy_quantity'], 2) 
                    if row['buy_quantity'] > 0 else 0.0, 
        axis=1
    )
    df_buy = df_buy.drop(columns=['buy_total_value'])
    
    # --- 4. 合併販售和收購結果 ---
    final_summary = pd.merge(df_sell, df_buy, on='item_name', how='outer').fillna(0)
    
    # 5. 清理欄位並重命名
    final_summary = final_summary.rename(columns={
        'sell_quantity': '總數量(販賣)',
        'buy_quantity': '總數量(收購)',
        'sell_min_price': '販賣最低價',
        'sell_max_price': '販賣最高價',
        'sell_avg_price': '販賣加權平均價',
        'buy_min_price': '收購最低價',
        'buy_max_price': '收購最高價',
        'buy_avg_price': '收購加權平均價'
    })
    
    # 選擇最終輸出的欄位順序 (並將價格四捨五入到整數，因為遊戲幣不常有小數點)
    final_summary = final_summary[[
        'item_name', 
        '總數量(販賣)', 
        '總數量(收購)', 
        '販賣最低價', 
        '販賣最高價', 
        '販賣加權平均價',
        '收購最低價', 
        '收購最高價', 
        '收購加權平均價'
    ]]
    
    # 將價格欄位轉為整數
    price_cols = ['販賣最低價', '販賣最高價', '販賣加權平均價', '收購最低價', '收購最高價', '收購加權平均價']
    for col in price_cols:
        # 使用 .astype(int) 轉換，但需要先將 0.0 轉換為 0
        final_summary[col] = final_summary[col].apply(lambda x: int(round(x)) if x > 0 else 0)
    
    # 7. 儲存到 CSV
    try:
        final_summary.to_csv(FILE_NAME, index=False, encoding='utf-8') 
        print(f"[{time.strftime('%H:%M:%S')}]  - ✅ 成功將 {len(final_summary)} 筆彙總記錄儲存到 **{FILE_NAME}**。")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}]  - ❌ 儲存彙總檔案失敗: {e}")

    # 8. (可選) 顯示彙總結果
    print("\n--- 本次彙總結果 (僅限純淨道具) ---")
    print(final_summary.to_markdown(index=False, floatfmt=".0f")) # 顯示時隱藏小數點
    print("----------------------------------\n")
# ----------------- 排程任務核心邏輯 (已修改) -----------------

def run_scraping_task(driver, SEARCH_ITEMS):
    """將多關鍵字爬蟲的邏輯包裝成一個獨立函式，用於排程。"""
    
    # 設置本次執行的統一時間戳 (YYYY/M/D/Hour)
    now = datetime.now()
    # 使用 YYYY/M/D/Hour 格式作為時間戳標記
    run_timestamp_for_file = now.strftime('%Y/%#m/%#d/%#H') # e.g., '2025/9/25/15'
    
    print("\n" + "="*80)
    print(" " * 28 + "【整點任務開始】")
    print(f" " * 28 + f"【排程時間戳: {run_timestamp_for_file}】")
    print("="*80)

    all_data_for_summary: list[AuctionItem] = [] # 用於收集本次所有爬到的資料
    total_records = 0

    try:
        # 嘗試一個簡單操作來檢查 Driver 是否有效
        driver.find_element(By.ID, "a_searchBtn").click() 
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, "div_svr")))
        print(f"[{time.strftime('%H:%M:%S')}] ✅ 成功回到搜尋主頁面。Driver 狀態正常。")
        time.sleep(1)

        for item_keyword in SEARCH_ITEMS:
            print("\n" + "#"*60)
            print(f"[{time.strftime('%H:%M:%S')}]  - 【開始處理關鍵字：{item_keyword.upper()}】")
            print("#"*60)
            
            # 執行第一頁查詢、解析並獲取總頁數
            initial_data, max_page = perform_search_and_get_page_count(driver, item_keyword)

            # 執行多頁爬取
            if max_page > 0:
                full_item_data = scrape_multiple_pages(driver, max_page, initial_data, item_keyword)
            else:
                full_item_data = initial_data
            
            # 將本次結果加入總清單
            all_data_for_summary.extend(full_item_data)
            total_records += len(full_item_data)
            print(f"[{time.strftime('%H:%M:%S')}]  - ✅ 關鍵字【{item_keyword}】數據收集完畢，總共 {len(full_item_data)} 筆資料。")

        # --- 新增：數據分析和儲存彙總 CSV ---
        if total_records > 0:
            analyze_and_save_summary(all_data_for_summary, run_timestamp_for_file)
        else:
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ 本次排程沒有爬取到任何記錄，跳過數據分析。")
        # ------------------------------------

        print(f"\n[{time.strftime('%H:%M:%S')}] ✨ **本次排程總計爬取 {total_records:,} 筆記錄。**")
        return True # 任務成功

    except WebDriverException as e:
        # 捕獲所有 WebDriver 相關錯誤，包括 'invalid session id'
        # ... (此處保留原始碼)
        print(f"[{time.strftime('%H:%M:%S')}] 🚨 爬蟲任務執行期間發生 WebDriver 錯誤: {e}")
        if "invalid session id" in str(e) or "disconnected" in str(e):
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ 偵測到 **Session 失效或瀏覽器斷線**，需要重啟 Driver。")
        else:
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ 非 Session 失效的一般 WebDriver 錯誤。")
        
        try:
            driver.get_screenshot_as_file(f"task_fail_{datetime.now().strftime('%H%M')}.png")
        except:
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ 無法截圖，Driver 可能已失效。")
        
        return False # 任務失敗，需重啟 Driver
        
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] 🚨 爬蟲任務執行期間發生其他錯誤: {e}")
        return True # 視為一次性的任務失敗，不一定需要重啟 Driver

# ----------------- 主流程：初始化、監控與重啟邏輯 -----------------

def scrape_cloudflare_protected_site(url: str):
    # ... (此處保留原始碼)
    
    # *** 定義要搜尋的道具清單 (可隨時修改) ***
    SEARCH_ITEMS = ["鋁", "大嘴鳥卡片", "神之金屬"] 
    driver = None
    
    # 將登入和瀏覽器初始化包裝成一個函式，方便重試
    def initialize_browser_and_login(current_driver):
        # ... (此處保留原始碼)
        non_local_driver = current_driver
        try:
            # 嘗試關閉舊的 driver
            if non_local_driver:
                print(f"[{time.strftime('%H:%M:%S')}] 🧹 正在嘗試關閉舊的瀏覽器 Driver...")
                try:
                    non_local_driver.quit()
                except:
                    pass
            
            print(f"[{time.strftime('%H:%M:%S')}] 🔄 正在初始化新的瀏覽器 Driver...")
            options = uc.ChromeOptions()
            non_local_driver = uc.Chrome(options=options)
            non_local_driver.get(url)
            print(f"[{time.strftime('%H:%M:%S')}] 🌐 嘗試訪問目標網址: {url}")
            time.sleep(3) 

            # 點擊登入連結並執行登入
            LOGIN_LINK_ID = "a_searchBtn"
            login_link = WebDriverWait(non_local_driver, 20).until(EC.element_to_be_clickable((By.ID, LOGIN_LINK_ID)))
            login_link.click()
            print(f"[{time.strftime('%H:%M:%S')}] 🔗 點擊 '請先登入' 成功，觸發登入彈出視窗。")
            login_success = perform_login(non_local_driver)
            
            return non_local_driver, login_success
            
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] ❌ 瀏覽器或登入初始化失敗: {e}")
            return non_local_driver, False

    # --- 首次初始化並登入 ---
    driver, login_success = initialize_browser_and_login(driver)
    
    try:
        # --- 步驟 2: 登入成功後，進入無限迴圈檢查排程 ---
        if login_success:
            last_hour = -1 # 初始化一個不可能的時間
            
            print("\n" + "="*80)
            print(" " * 20 + "【進入整點排程監控模式】")
            print(" " * 15 + "程式將持續運行，整點時自動執行爬蟲任務...")
            print("="*80)
            
            while True:
                now = datetime.now()
                current_minute = now.minute
                current_hour = now.hour
                
                # 檢查是否為整點 (分鐘數為 0) 且該小時尚未執行過
                if current_minute == 0 and current_hour != last_hour:
                # if True:
                    print(f"\n[{now.strftime('%H:%M:%S')}] 🔔 偵測到整點 {now.strftime('%H:00')}，啟動爬蟲任務...")
                    
                    # 執行任務
                    task_success = run_scraping_task(driver, SEARCH_ITEMS)
                    
                    if not task_success:
                        # 如果 run_scraping_task 失敗並返回 False (代表 session 失效)，則重啟並重新登入
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 任務失敗，嘗試重新初始化瀏覽器並登入...")
                        driver, login_success = initialize_browser_and_login(driver)
                        
                        if not login_success:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] 致命錯誤: 重啟後登入再次失敗，退出程式。")
                            break # 退出 while True 迴圈
                        else:
                            # 重新登入成功，仍然更新 last_hour，防止本小時重複執行
                            last_hour = current_hour
                    else:
                        last_hour = current_hour # 任務成功，更新已執行的小時
                        
                    # 執行完畢後，等待 60 秒再進行下一次檢查
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 😴 任務完成，等待 60 秒後繼續監控...")
                    time.sleep(60) 

                else:
                    # 非整點時，等待直到下一分鐘
                    sleep_time = 60 - now.second
                    # 確保在 XX:59:XX 時，能進入整點檢查
                    if current_minute == 59 and current_hour != last_hour:
                        sleep_time += 1 
                        
                    # 輸出訊息並停頓
                    print(f"\r[{now.strftime('%H:%M:%S')}] ⏰ 非整點，{current_minute:02d}分，等待 {sleep_time} 秒...", end="")
                    time.sleep(sleep_time)

        else:
            print(f"[{time.strftime('%H:%M:%S')}] 😥 登入失敗，程式停止。")

    except Exception as e:
        print(f"[{time.strftime('%H:%M:%M')}] 🚨 總流程發生錯誤: {e}")
        
    finally:
        # 確保在程式結束時關閉瀏覽器
        print("\n\n按下 Enter 鍵關閉瀏覽器並結束程式...")
        input()
        if driver:
            try:
                driver.quit() 
            except:
                pass
        print(f"[{time.strftime('%H:%M:%S')}] 瀏覽器已關閉。" )


# --- 執行程式碼 ---
if __name__ == '__main__':
    target_url = "https://event.gnjoy.com.tw/RoZ/RoZ_ShopSearch" 
    scrape_cloudflare_protected_site(target_url)