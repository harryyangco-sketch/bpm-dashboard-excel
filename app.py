from pathlib import Path
from datetime import datetime, timezone, timedelta
import json

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

st.set_page_config(
    page_title="BPM Team Project Management Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 隱藏 Streamlit 預設的 header/footer，讓 dashboard 滿版呈現
st.markdown(
    """
    <style>
      #MainMenu, header, footer {visibility: hidden;}
      .block-container {padding: 0.6rem 1rem 0 !important; max-width: 100% !important;}
      iframe {display: block; width: 100%; border: none;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ── 更新資料按鈕（原生 Streamlit 元件，放在 iframe 外面）──
# 清快取＋重新執行整份腳本，確保重新讀取 tasks.xlsx 最新內容
# （repo 更新後 Streamlit Cloud 會自動重新部署一次；這顆按鈕是給
# 「同一次部署內，剛剛才 push 新版 Excel」這種情況用的手動保險）。
col1, _ = st.columns([1, 9])
with col1:
    if st.button("🔄 更新資料"):
        st.cache_data.clear()
        st.rerun()

EXCEL_PATH = Path(__file__).parent / "tasks.xlsx"


def to_date_str(val):
    """把 Excel 讀出來的日期值統一轉成 'YYYY-MM-DD' 字串，或 None。
    Excel 儲存格可能是純文字（我們範本預設如此），也可能被使用者
    不小心輸入成真正的日期型別，這裡兩種狀況都處理。"""
    if pd.isna(val) or val == "":
        return None
    if isinstance(val, (pd.Timestamp, datetime)):
        return val.strftime("%Y-%m-%d")
    return str(val).strip() or None


def to_text(val):
    if pd.isna(val):
        return ""
    return str(val).strip()


@st.cache_data(ttl=60)
def load_tasks():
    df = pd.read_excel(EXCEL_PATH, sheet_name="Tasks")
    df = df.dropna(how="all")  # 忽略完全空白的列

    tasks = []
    for _, row in df.iterrows():
        proj = to_text(row.get("專案"))
        task_name = to_text(row.get("任務名稱"))
        if not proj or not task_name:
            continue  # 專案或任務名稱沒填的列視為無效，跳過

        status = to_text(row.get("狀態")) or "未開始"
        start_val = row.get("起始值")
        end_val = row.get("結束值")
        start_val = 0 if pd.isna(start_val) else float(start_val)
        end_val = 100 if pd.isna(end_val) else float(end_val)

        if status == "已完成":
            progress = 100
        elif status == "未開始":
            progress = 0
        else:
            progress = round(start_val / end_val * 100) if end_val else 0

        tasks.append({
            "proj": proj,
            "task": task_name,
            "owner": to_text(row.get("負責人")),
            "prio": to_text(row.get("優先順序")),
            "status": status,
            "start": to_date_str(row.get("開始日期")),
            "end": to_date_str(row.get("結束日期")),
            "progress": progress,
            "decide": to_text(row.get("須優先決議")) or "否",
            "note": to_text(row.get("決議事項說明")),
            "prog_note": to_text(row.get("進度說明")),
            "actual_end": to_date_str(row.get("實際完成日")),
        })
    return tasks


if not EXCEL_PATH.exists():
    st.error(f"找不到 {EXCEL_PATH.name}，請確認它和 app.py 放在 repo 同一層。")
    st.stop()

try:
    with st.spinner("讀取 tasks.xlsx 中..."):
        tasks = load_tasks()
except Exception as e:
    st.error(f"讀取 tasks.xlsx 時發生錯誤：{e}")
    st.stop()

if not tasks:
    st.error("tasks.xlsx 裡沒有讀到任何有效任務，請確認「專案」「任務名稱」欄位都有填。")
    st.stop()

today_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")

tasks_json = json.dumps(tasks, ensure_ascii=False)
# 防護：若儲存格內容剛好包含 "</script>"，未跳脫會提前關閉整段 <script>，
# 導致頁面壞掉甚至有 XSS 風險，因此把 "</" 轉成 JS 可安全解析的 "<\/"。
tasks_json = tasks_json.replace("</", "<\\/")

HTML_PATH = Path(__file__).parent / "dashboard.html"
if not HTML_PATH.exists():
    st.error(f"找不到 {HTML_PATH.name}，請確認它和 app.py 放在 repo 同一層。")
    st.stop()

html = HTML_PATH.read_text(encoding="utf-8")
html = html.replace("__SNAPSHOT_DATETIME__", today_str)
html = html.replace("__TASKS_JSON__", tasks_json)

# scrolling=False + dashboard.html 內建的自動調整高度腳本（直接改 iframe 自身高度），
# 讓 iframe 高度跟著內容撐開，只留瀏覽器外層一條滑軌（不會有內外兩條）。
# height=1200 只是「JS 校正前」的暫時高度，避免一開始閃一下被裁切；
# 實際高度會在頁面載入後由 dashboard.html 裡的 postHeight() 自動調整成正確值。
components.html(html, height=1200, scrolling=False)
