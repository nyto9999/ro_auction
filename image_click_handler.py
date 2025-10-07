import cv2
import numpy as np
from PIL import Image
from io import BytesIO
import os
import time
from datetime import datetime 

# 樣板圖片的路徑
CHECKBOX_TEMPLATE_PATH = "checkbox_template.png"

def save_debug_screenshot(screenshot_buffer: bytes, max_loc: tuple, w: int, h: int, max_val: float):
    """將瀏覽器截圖和最佳匹配框線儲存為偵錯圖片。"""
    try:
        # 1. 載入並轉換截圖
        screenshot_pil = Image.open(BytesIO(screenshot_buffer)).convert("RGB")
        screenshot_np = np.array(screenshot_pil)
        # 轉換為 BGR 格式，OpenCV 才能正確繪圖和儲存
        screenshot_cv = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR) 

        # 2. 計算 bounding box 座標
        top_left_x, top_left_y = max_loc
        bottom_right_x = top_left_x + w
        bottom_right_y = top_left_y + h

        # 3. 繪製矩形框線 (綠色)
        color = (0, 255, 0) # BGR: 綠色
        thickness = 3
        cv2.rectangle(screenshot_cv, (top_left_x, top_left_y), (bottom_right_x, bottom_right_y), color, thickness)
        
        # 4. 繪製相關係數文字
        text = f"Match: {max_val:.4f}"
        cv2.putText(screenshot_cv, text, (top_left_x, top_left_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # 5. 儲存檔案
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_filename = f"debug_match_{timestamp}.png"
        
        cv2.imwrite(debug_filename, screenshot_cv)
        print(f"[{time.strftime('%H:%M:%S')}] ⚠️ 匹配失敗，已保存偵錯截圖至：{debug_filename} (最高相關係數: {max_val:.4f})")
        
    except Exception as e:
        print(f"🚨 儲存偵錯截圖時發生錯誤: {e}")


def find_template_on_screenshot(screenshot_buffer: bytes, template_path: str, threshold: float = 0.50) -> tuple[int, int, int, int] | None:
    """
    在瀏覽器截圖中尋找樣板圖片的位置。
    # 閾值已降為 0.50
    """
    if not os.path.exists(template_path):
        print(f"❌ 錯誤：找不到樣板圖片：{template_path}。請確認已放置。")
        return None
        
    try:
        # 1. 讀取截圖和樣板
        screenshot_pil = Image.open(BytesIO(screenshot_buffer)).convert("RGB")
        screenshot_np = np.array(screenshot_pil)
        
        template_np = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
        
        if template_np is None:
            return None
            
        screenshot_gray = cv2.cvtColor(cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2GRAY)

        w, h = template_np.shape[1], template_np.shape[0]

        # 2. 執行樣板匹配
        result = cv2.matchTemplate(screenshot_gray, template_np, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        # 3. 檢查匹配結果
        if max_val >= threshold:
            top_left_x, top_left_y = max_loc
            return top_left_x, top_left_y, w, h
        else:
            # === 呼叫偵錯儲存 (失敗時拍照) ===
            save_debug_screenshot(screenshot_buffer, max_loc, w, h, max_val)
            return None
            
    except Exception as e:
        print(f"🚨 圖像識別發生錯誤: {e}")
        return None


def locate_checkbox_and_get_center_coords(driver, template_path: str = CHECKBOX_TEMPLATE_PATH) -> tuple[int, int] | None:
    """
    在當前 Iframe 內截圖，使用圖像識別找到 Checkbox 的中心座標。
    """
    try:
        # 1. 獲取 Iframe 內部的截圖
        screenshot_buffer = driver.get_screenshot_as_png()
        
        # 2. 尋找樣板
        match = find_template_on_screenshot(screenshot_buffer, template_path)
        
        if match:
            x, y, w, h = match
            center_x = x + w // 2
            center_y = y + h // 2
            return center_x, center_y
            
        return None
        
    except Exception as e:
        print(f"🚨 執行定位發生錯誤 (無法截圖 Iframe 內容): {e}")
        return None
