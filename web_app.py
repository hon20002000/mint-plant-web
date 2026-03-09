#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import pathlib
from datetime import datetime

import pandas as pd
import streamlit as st

# ============ 路徑與檔案設定 ============

BASE_DIR = pathlib.Path(__file__).parent
STATE_JSON = BASE_DIR / "latest_state.json"
XLSX_FILE = BASE_DIR / "plant_data.xlsx"

FACES_DIR = BASE_DIR / "faces"  # 放各種表情圖片的資料夾

MOOD_IMAGE_MAP = {
    "happy": "happy.png",
    "calm": "calm.png",
    "sad": "sad.png",
    "sick": "sick.png",
    "hot": "hot.png",
    "cold": "cold.png",
    "lonely": "lonely.png",
}
DEFAULT_IMAGE = "calm.png"

# ============ 頁面與自動刷新設定 ============

st.set_page_config(
    page_title="Mint Plant Pet",
    page_icon="🌱",
    layout="centered",
)

# 利用 query_param 觸發 Streamlit 重新運行（部署在雲端時可改為 st_autorefresh）
# st.experimental_set_query_params(ts=datetime.utcnow().isoformat())
st.query_params["ts"] = datetime.utcnow().isoformat()

st.title("🌱 薄荷植物寵物儀表板")

# ============ 讀取最新狀態（優先 JSON，其次 Excel） ============

state = None

if STATE_JSON.exists():
    try:
        with open(STATE_JSON, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception as e:
        st.warning(f"讀取 latest_state.json 時發生錯誤，將改用 Excel：{e}")

if state is None:
    if not XLSX_FILE.exists():
        st.warning("尚未找到 `plant_data.xlsx` 或 `latest_state.json`，請先在本地執行感測系統（app.py）產生資料。")
        st.stop()
    try:
        df = pd.read_excel(XLSX_FILE)
    except Exception as e:
        st.error(f"讀取 Excel 時發生錯誤：{e}")
        st.stop()
    if df.empty:
        st.warning("Excel 目前沒有資料，請先讓 app.py 運行一段時間。")
        st.stop()
    latest = df.iloc[-1]
    state = {
        "timestamp": latest.get("timestamp"),
        "soil": latest.get("soil"),
        "light": latest.get("light"),
        "temp": latest.get("temp"),
        "hum": latest.get("hum"),
        "H_sensor": latest.get("H_sensor"),
        "H_image": latest.get("H_image"),
        "H_total": latest.get("H_total"),
        "mood": None if pd.isna(latest.get("mood")) else str(latest.get("mood")),
        "level": latest.get("level"),
    }

# 安全解析欄位
ts = state.get("timestamp")
soil = state.get("soil")
light = state.get("light")
temp = state.get("temp")
hum = state.get("hum")
H_sensor = state.get("H_sensor")
H_image = state.get("H_image")
H_total = state.get("H_total")
mood = state.get("mood") or "calm"
level = state.get("level")

# ============ 上半部：表情圖片 + 核心指標 ============

col1, col2 = st.columns([1, 1])

with col1:
    img_name = MOOD_IMAGE_MAP.get(mood, DEFAULT_IMAGE)
    img_path = FACES_DIR / img_name
    if img_path.exists():
        st.image(str(img_path), width=220)
    else:
        st.write(f"找不到對應表情圖片：`faces/{img_name}`")
        st.write("請確認你已在 repo 的 faces/ 目錄中上傳這張圖。")

with col2:
    st.markdown(f"### 目前心情：**{mood}**")
    if isinstance(level, str):
        st.write(f"健康狀態等級：{level}")
    if isinstance(ts, str):
        st.write(f"最後更新時間：{ts}")

    st.write("### 健康指標")
    c1, c2, c3 = st.columns(3)
    c1.metric("H_sensor", f"{H_sensor:.1f}" if isinstance(H_sensor, (int, float)) else "--")
    c2.metric("H_image", f"{H_image:.1f}" if isinstance(H_image, (int, float)) else "--")
    c3.metric("H_total", f"{H_total:.1f}" if isinstance(H_total, (int, float)) else "--")

# ============ 下半部：環境數據與歷史趨勢 ============

st.markdown("### 當前環境與感測數據")

st.write(
    f"- 土壤濕度 soil：**{soil}**\n"
    f"- 光照強度 light：**{light}**\n"
    f"- 溫度 temp：**{temp} °C**\n"
    f"- 空氣濕度 hum：**{hum} %**"
)

st.markdown("### 歷史健康趨勢（來自 Excel 記錄）")

if XLSX_FILE.exists():
    try:
        hist_df = pd.read_excel(XLSX_FILE)
        if not hist_df.empty:
            # 嘗試把 timestamp 轉成時間軸
            try:
                hist_df["timestamp"] = pd.to_datetime(hist_df["timestamp"])
                hist_df = hist_df.set_index("timestamp")
            except Exception:
                pass

            cols = [c for c in ["H_sensor", "H_image", "H_total"] if c in hist_df.columns]
            if cols:
                st.line_chart(hist_df[cols], height=260)
            else:
                st.info("Excel 中尚未找到 H_sensor / H_image / H_total 欄位。")
        else:
            st.info("Excel 目前沒有歷史資料。")
    except Exception as e:
        st.warning(f"讀取歷史資料時發生錯誤：{e}")
else:
    st.info("尚未產生 Excel 檔案。")

st.markdown("---")
st.caption("本頁面由本地感測與 YOLO 模型的最新狀態生成。請確保本地 app.py 正在運行以持續更新資料。")
