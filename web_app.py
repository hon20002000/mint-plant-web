#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import pathlib

import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ============ 路徑與圖像設定 ============

BASE_DIR = pathlib.Path(__file__).parent
CLOUD_STATE_JSON = BASE_DIR / "cloud_state.json"
FACES_DIR = BASE_DIR / "faces"

MOOD_IMAGE_MAP = {
    "happy": "happy.png",
    "calm": "calm.png",
    "sad": "sad.png",
    "hot": "hot.png",
    "cold": "cold.png",
    "dry": "dry.png",
    "moist": "moist.png",
    "curious": "curious.png",
}
DEFAULT_IMAGE = "calm.png"

# ============ Streamlit 頁面設定 ============

st.set_page_config(
    page_title="Mint Plant Pet (Cloud)",
    page_icon="🌱",
    layout="centered",
)

st.title("🌱 薄荷植物寵物儀表板（雲端快照版）")

# 每 10 秒自動重新整理一次
st_autorefresh(interval=10_000, key="auto_refresh")

# ============ 讀取 cloud_state.json ============

if not CLOUD_STATE_JSON.exists():
    st.warning("尚未找到 cloud_state.json。\n\n請確認本地 app.py 正在運行，並成功同步狀態到 GitHub。")
    st.stop()

try:
    with open(CLOUD_STATE_JSON, "r", encoding="utf-8") as f:
        state = json.load(f)
except Exception as e:
    st.error(f"讀取 cloud_state.json 時發生錯誤：{e}")
    st.stop()

if not isinstance(state, dict) or not state:
    st.warning("cloud_state.json 內容為空，請稍後再試。")
    st.stop()

# ============ 解析狀態欄位 ============

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
dialog = state.get("dialog")

# ============ 分頁：總覽 / 感測數據 ============

tab_overview, tab_env = st.tabs(["🌿 植物狀態總覽", "📊 環境感測數據"])

# ---- 頁籤 1：臉 + 心情 + 指標 ----
with tab_overview:
    col1, col2 = st.columns([1, 1])

    with col1:
        img_name = MOOD_IMAGE_MAP.get(mood, DEFAULT_IMAGE)
        img_path = FACES_DIR / img_name
        if img_path.exists():
            st.image(str(img_path), width=220)
        else:
            st.write(f"找不到對應表情圖片：faces/{img_name}")
            st.write("請確認你已在 repo 的 faces/ 目錄中上傳這張圖。")

    with col2:
        st.markdown(f"### 目前心情：**{mood}**")

        if isinstance(dialog, str):
            st.markdown(f"**植物說：** {dialog}")

        if isinstance(level, str):
            st.write(f"健康狀態等級：{level}")

        st.write("### 健康指標")
        c1, c2, c3 = st.columns(3)
        c1.metric("H_sensor", f"{H_sensor:.1f}" if isinstance(H_sensor, (int, float)) else "--")
        c2.metric("H_image", f"{H_image:.1f}" if isinstance(H_image, (int, float)) else "--")
        c3.metric("H_total", f"{H_total:.1f}" if isinstance(H_total, (int, float)) else "--")

    st.caption(
        "本頁顯示的是來自 GitHub cloud_state.json 的最新狀態快照。\n"
        "本地 app.py 約每 30 秒同步一次狀態，本頁每 10 秒自動刷新。"
    )

# ---- 頁籤 2：環境感測數據 ----
with tab_env:
    st.markdown("### 當前環境與感測數據")
    st.write(
        f"- 土壤濕度 soil：**{soil}**\n"
        f"- 光照強度 light：**{light}**\n"
        f"- 溫度 temp：**{temp} °C**\n"
        f"- 空氣濕度 hum：**{hum} %**"
    )
