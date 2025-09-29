import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import numpy as np 
from datetime import timedelta
import glob 
import re 

# --- 1. 配置與數據載入 (僅保留最高/最低價的欄位映射) ---

# 定義彙總檔案的欄位映射
SUMMARY_COL_MAP = {
    '總數量(收購)': 'volume_收購',
    '總數量(販賣)': 'volume_販售',
    '收購最低價': 'min_收購',
    '收購最高價': 'max_收購',
    '販賣最低價': 'min_販售',
    '販賣最高價': 'max_販售',
}

def load_and_preprocess_data(item_name_to_plot):
    """
    掃描資料夾中所有【_summary.csv】檔案，彙總特定道具的數據，
    並將檔案名稱中的時間解析為 'hour' 索引。
    """
    all_summary_files = glob.glob("*_summary.csv") 
    
    if not all_summary_files:
        print(f"錯誤: 在當前目錄中找不到任何小時彙總檔案 (*_summary.csv)。")
        return None 

    df_list = []
    
    # 擴充映射以處理舊檔案中的 avg 欄位，但我們會在最後捨棄它
    temp_col_map = {**SUMMARY_COL_MAP, 
                    '收購加權平均價': 'avg_收購_temp', 
                    '販賣加權平均價': 'avg_販售_temp'}
    
    print(f"🔍 掃描到 {len(all_summary_files)} 個小時彙總檔案，正在載入...")

    for filename in all_summary_files:
        try:
            match = re.search(r'(\d{4}_\d{1,2}_\d{1,2}_\d{1,2})', filename)
            if not match:
                 continue
            
            timestamp_str = match.group(1).replace('_', '-')
            hour_start = pd.to_datetime(timestamp_str, format='%Y-%m-%d-%H', errors='coerce')
            
            if pd.isna(hour_start):
                 continue
            
            df = pd.read_csv(filename)
            
            df = df[df['item_name'] == item_name_to_plot].copy()
            if df.empty:
                continue 

            # 使用臨時映射來重命名欄位，這樣即使檔案中有 avg 欄位也不會出錯
            df = df.rename(columns={k: v for k, v in temp_col_map.items() if k in df.columns})
            
            df['hour'] = hour_start 
            df = df.set_index('hour')
            df_list.append(df)
            
        except Exception as e:
            print(f"警告: 讀取或處理檔案 {filename} 時發生錯誤: {e}，已跳過。")
            continue

    if not df_list:
        print(f"警告: 找不到道具【{item_name_to_plot}】的有效彙總數據。")
        return None

    combined_df = pd.concat(df_list).sort_index()
    
    required_cols = list(SUMMARY_COL_MAP.values())
    
    # 確保所有需要的欄位都存在
    for col in required_cols:
        if col not in combined_df.columns:
            combined_df[col] = 0 if 'volume' in col else np.nan
    
    # 過濾只保留需要的欄位 (不包含 avg_temp 欄位)
    combined_df = combined_df[required_cols]

    # 價格欄位前向填充 (ffill)
    price_cols = [col for col in required_cols if '價' in col]
    combined_df[price_cols] = combined_df[price_cols].ffill()
    
    # 數量欄位填充 0
    volume_cols = [col for col in required_cols if 'volume' in col]
    combined_df[volume_cols] = combined_df[volume_cols].fillna(0)
    
    combined_df = combined_df.resample('H').asfreq()
    
    return combined_df


# --- 2. 核心繪圖函數 (新增歷史平均水平線與統一標記點) ---

def plot_combined_trends_plotly(summary_df, item_name):
    """
    使用 Plotly 繪製三子圖：收購價、販售價 (包含歷史平均水平線)，以及堆疊交易量。
    【核心修正】：移除小時加權平均線，新增四條歷史平均水平參考線。
    """
    
    fig = make_subplots(
        rows=3, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.05, 
        subplot_titles=(
            f'【收購】價格趨勢 (含歷史平均價格)', # <-- 標題更新
            f'【販售】價格趨勢 (含歷史平均價格)', # <-- 標題更新
            '小時【交易量】趨勢 (收購/販售堆疊)' 
        ),
        specs=[
            [{"secondary_y": False}], 
            [{"secondary_y": False}], 
            [{"secondary_y": False}] 
        ]
    )
    
    # --- 歷史平均計算 (步驟 1) ---
    # 使用非零平均數 (Mean of the respective columns across ALL hours)
    df_temp = summary_df.replace({0: np.nan}) 
    
    # 歷史最高/最低收購價的平均值
    avg_buy_max_price = df_temp['max_收購'].mean()
    avg_buy_min_price = df_temp['min_收購'].mean()
    
    # 歷史最高/最低販售價的平均值
    avg_sell_max_price = df_temp['max_販售'].mean()
    avg_sell_min_price = df_temp['min_販售'].mean()
    
    # --- 顏色定義與樣式 (步驟 2) ---
    
    # 收購 (綠色調)
    COLOR_BUY_TREND = '#008000'       # 綠色 (最高/最低價趨勢線)
    COLOR_BUY_AVG_REF = '#3CB371'     # 較淺的綠色 (歷史平均參考線)
    
    # 販售 (紅色調)
    COLOR_SELL_TREND = '#B22222'      # 紅色 (最高/最低價趨勢線)
    COLOR_SELL_AVG_REF = '#FA8072'     # 較淺的紅色 (歷史平均參考線)

    # 價格線配置函式 (包含標記點)
    def line_config_with_marker(color, dash_style, width=3):
        return dict(
            mode='lines+markers', 
            line=dict(color=color, dash=dash_style, shape='spline', width=width),
            marker=dict(size=5, symbol='circle', line=dict(width=1, color='DarkSlateGrey')) 
        )
    
    # ----------------------------------------------------
    # ====== Row 1: 收購價格 (Max/Min Buy Price & Historical Avg) ======
    # ----------------------------------------------------
    
    # 1. 最高價趨勢線 (實線)
    fig.add_trace(go.Scatter(x=summary_df.index, y=summary_df['max_收購'], name='收購最高價', 
                             **line_config_with_marker(COLOR_BUY_TREND, 'solid')), row=1, col=1)
    # 2. 最低價趨勢線 (虛線)
    fig.add_trace(go.Scatter(x=summary_df.index, y=summary_df['min_收購'], name='收購最低價', 
                             **line_config_with_marker(COLOR_BUY_TREND, 'dot')), row=1, col=1) 
    
    # 3. 歷史平均參考線 (水平線)
    # 最高價歷史平均 (虛線)
    if not np.isnan(avg_buy_max_price):
        fig.add_shape(type="line", x0=summary_df.index.min(), x1=summary_df.index.max(), 
                      y0=avg_buy_max_price, y1=avg_buy_max_price, 
                      line=dict(color=COLOR_BUY_AVG_REF, width=2, dash="dash"),
                      name=f"Max Avg: {avg_buy_max_price:,.0f}", row=1, col=1)
        fig.add_annotation(xref="x domain", yref="y", x=1.00, y=avg_buy_max_price, row=1, col=1,
                           text=f"Max Avg: {avg_buy_max_price:,.0f}", showarrow=False,
                           font=dict(color=COLOR_BUY_AVG_REF, size=10), xanchor='left', yanchor='middle')
    
    # 最低價歷史平均 (點線)
    if not np.isnan(avg_buy_min_price):
        fig.add_shape(type="line", x0=summary_df.index.min(), x1=summary_df.index.max(), 
                      y0=avg_buy_min_price, y1=avg_buy_min_price, 
                      line=dict(color=COLOR_BUY_AVG_REF, width=2, dash="dot"),
                      name=f"Min Avg: {avg_buy_min_price:,.0f}", row=1, col=1)
        fig.add_annotation(xref="x domain", yref="y", x=1.00, y=avg_buy_min_price, row=1, col=1,
                           text=f"Min Avg: {avg_buy_min_price:,.0f}", showarrow=False,
                           font=dict(color=COLOR_BUY_AVG_REF, size=10), xanchor='left', yanchor='middle')

    fig.update_yaxes(title_text='收購價格 (Zeny)', row=1, col=1, tickformat=',.0f', 
                     fixedrange=True, side='right', gridcolor='#E0E0E0', title_font=dict(size=14)) 
    
    
    # ----------------------------------------------------
    # ====== Row 2: 販售價格 (Min/Max Sell Price & Historical Avg) ======
    # ----------------------------------------------------
    
    # 1. 最低價趨勢線 (虛線)
    fig.add_trace(go.Scatter(x=summary_df.index, y=summary_df['min_販售'], name='販售最低價', 
                             **line_config_with_marker(COLOR_SELL_TREND, 'dot')), row=2, col=1)
    # 2. 最高價趨勢線 (實線)
    fig.add_trace(go.Scatter(x=summary_df.index, y=summary_df['max_販售'], name='販售最高價', 
                             **line_config_with_marker(COLOR_SELL_TREND, 'solid')), row=2, col=1) 
    
    # 3. 歷史平均參考線 (水平線)
    # 最高價歷史平均 (虛線)
    if not np.isnan(avg_sell_max_price):
        fig.add_shape(type="line", x0=summary_df.index.min(), x1=summary_df.index.max(), 
                      y0=avg_sell_max_price, y1=avg_sell_max_price, 
                      line=dict(color=COLOR_SELL_AVG_REF, width=2, dash="dash"),
                      name=f"Max Avg: {avg_sell_max_price:,.0f}", row=2, col=1)
        fig.add_annotation(xref="x domain", yref="y", x=1.00, y=avg_sell_max_price, row=2, col=1,
                           text=f"Max Avg: {avg_sell_max_price:,.0f}", showarrow=False,
                           font=dict(color=COLOR_SELL_AVG_REF, size=10), xanchor='left', yanchor='middle')
    
    # 最低價歷史平均 (點線)
    if not np.isnan(avg_sell_min_price):
        fig.add_shape(type="line", x0=summary_df.index.min(), x1=summary_df.index.max(), 
                      y0=avg_sell_min_price, y1=avg_sell_min_price, 
                      line=dict(color=COLOR_SELL_AVG_REF, width=2, dash="dot"),
                      name=f"Min Avg: {avg_sell_min_price:,.0f}", row=2, col=1)
        fig.add_annotation(xref="x domain", yref="y", x=1.00, y=avg_sell_min_price, row=2, col=1,
                           text=f"Min Avg: {avg_sell_min_price:,.0f}", showarrow=False,
                           font=dict(color=COLOR_SELL_AVG_REF, size=10), xanchor='left', yanchor='middle')

    fig.update_yaxes(title_text='販售價格 (Zeny)', row=2, col=1, tickformat=',.0f', 
                     fixedrange=True, side='right', gridcolor='#E0E0E0', title_font=dict(size=14))
    
    
    # ----------------------------------------------------
    # ====== Row 3: 堆疊交易量 (Stacked Volume) ======
    # ----------------------------------------------------
    
    fig.add_trace(go.Bar(x=summary_df.index, y=summary_df['volume_收購'], name='收購數量', marker_color=COLOR_BUY_TREND, 
                         hovertemplate='<b>時間:</b> %{x|%m/%d %H:%M}<br><b>收購數量:</b> %{y:,} 個<extra></extra>'), row=3, col=1) 
    fig.add_trace(go.Bar(x=summary_df.index, y=summary_df['volume_販售'], name='販售數量', marker_color=COLOR_SELL_TREND, 
                         hovertemplate='<b>時間:</b> %{x|%m/%d %H:%M}<br><b>販售數量:</b> %{y:,} 個<extra></extra>'), row=3, col=1) 
    
    fig.update_layout(barmode='stack')
    fig.update_yaxes(title_text='交易量', row=3, col=1, tickformat=',.0f', 
                     fixedrange=True, side='right', gridcolor='#E0E0E0', title_font=dict(size=14))

    # ----------------------------------------------------
    # ====== 總體佈局設置 ======
    # ----------------------------------------------------
    time_controls = dict(
        rangeslider=dict(visible=True, thickness=0.08), 
        rangeselector=dict(buttons=list([
            dict(count=1, label="1小時", step="hour", stepmode="backward"), 
            dict(count=6, label="6小時", step="hour", stepmode="backward"), 
            dict(count=1, label="1天", step="day", stepmode="backward"),
            dict(count=7, label="7天", step="day", stepmode="backward"),
            dict(step="all")
        ]))
    )
    
    fig.update_layout(
        template='plotly_white', 
        font=dict(family="Arial, sans-serif", size=12, color="black"),
        title_text=f'**{item_name}** 市場分析趨勢 (價格區間 & 歷史平均價格)',
        title_x=0.5,
        height=900, 
        hovermode="x unified",
        margin=dict(r=100, l=80, b=100), 
        xaxis3={**time_controls, **dict(showticklabels=True, fixedrange=False, showgrid=False, title_text='時間 (小時)')},
        xaxis1=dict(matches='x3', showticklabels=False, fixedrange=False, showgrid=False),
        xaxis2=dict(matches='x3', showticklabels=False, fixedrange=False, showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        modebar_remove=['zoom', 'pan', 'select', 'lasso', 'autoscale', 'togglehover']
    )
    
    fig.show() 
    
    # === 步驟 1: 新增導出 HTML 程式碼 ===
    output_filename = f"{item_name}_市場分析.html"
    
    try:
        # 使用 write_html 儲存為獨立 HTML 文件
        fig.write_html(
            output_filename,
            include_plotlyjs='cdn', # 使用 CDN 載入 Plotly.js，減小檔案大小
            full_html=True
        )
        print(f"\n圖表已成功保存為 HTML 文件: {output_filename}")
        print(f"您可以將此文件直接分享給任何人，他們用瀏覽器即可打開交互！")
    except Exception as e:
        print(f"錯誤: 導出 HTML 失敗: {e}")
        
    return fig

# --- 3. 整合的主函數 (保持不變) ---

def generate_market_plot(item_name_to_plot):
    """
    主函式：載入、處理並繪製指定道具的市場趨勢圖。
    
    參數:
        item_name_to_plot (str): 要繪製的道具名稱。
    """
    print(f"📊 正在準備繪製【{item_name_to_plot}】的市場趨勢圖...")
    
    summary_df = load_and_preprocess_data(item_name_to_plot)
    
    if summary_df is None or summary_df.empty:
        print("警告: 數據為空或處理失敗，無法繪圖。")
        return None
        
    print(f"✅ 數據處理完成，共有 {len(summary_df)} 個小時的數據點。")
    
    fig = plot_combined_trends_plotly(summary_df, item_name_to_plot)
    
    print("\n🎉 繪圖完成。圖表已更新：**只包含最高/最低價趨勢線**，並新增了四條**歷史平均水平參考線** (最高價平均和最低價平均)。")
    return fig

# --- 執行範例 ---

if __name__ == "__main__":
    # 您可以修改這裡的道具名稱來繪製不同的圖表
    ITEM_TO_PLOT = "神之金屬" 
    
    # 呼叫整合後的函數
    generate_market_plot(ITEM_TO_PLOT)