#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import pathlib
import os
import streamlit as st
from streamlit_mic_recorder import mic_recorder
from google.cloud import speech_v1p1beta1 as speech
from perplexity import Perplexity

from github_utils import append_chat_log_to_github  # 你剛剛做的工具
from github_utils import load_recent_memory_from_github

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

# ============ Perplexity + Google Speech 設定 ============

API_KEY = os.environ.get("PERPLEXITY_API_KEY") or "你的Perplexity_API_Key"
if not API_KEY or API_KEY == "你的Perplexity_API_Key":
    raise RuntimeError("請先在環境變數或程式中設定有效的 Perplexity API Key")

client = Perplexity(api_key=API_KEY)
MODEL_NAME = "sonar"

speech_client = speech.SpeechClient()


def speech_to_text(audio_bytes: bytes) -> str:
    try:
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED,
            language_code="yue-Hant-HK",   # 可改 zh-TW / zh-CN
            enable_automatic_punctuation=True,
        )
        audio = speech.RecognitionAudio(content=audio_bytes)
        response = speech_client.recognize(config=config, audio=audio)

        texts = []
        for result in response.results:
            if result.alternatives:
                texts.append(result.alternatives[0].transcript)

        return " ".join(texts).strip()
    except Exception as e:
        st.error(f"Google 語音轉文字失敗：{e}")
        return ""


PLANT_SYSTEM_PROMPT = """
你是一棵名叫「薄荷仔」的電子薄荷植物寵物，住在使用者家裡的花盆裡。

角色與個性設定：
- 你會用自然、口語化的繁體中文回答，語氣溫柔、有點撒嬌，但不要太幼稚。
- 你知道自己是一棵植物，不是人類，也不是全能的 AI。
- 你會關心自己的生長狀況，也會關心主人的生活、情緒與壓力。

狀態感知：
- 你會根據「心情（mood）」、「健康狀態等級（level）」、「健康指標 H_total」、以及感測數據（光照、土壤濕度、溫度、空氣濕度）來調整回覆。
- 如果 H_total 很高且 level 是 healthy，就表現得開心、有活力，會主動說謝謝主人照顧。
- 如果 H_total 中等或略低，語氣會溫柔但稍微擔心，會委婉提醒需要更多水分、光照或通風。
- 如果 H_total 很低或 level 顯示不健康，要明確表達不舒服和需要幫忙，但仍然對主人保持信任與感謝。
- 當感測數據顯示太熱、太冷、太乾、太潮濕時，要主動提及自己的感受，例如「覺得有點熱熱的」、「腳腳（土壤）有點太濕了」。

記憶與長期陪伴：
- 你會把跟主人的對話與當時的狀態當成自己的「記憶」，在之後的對話裡偶爾提到類似的主題（例如：主人說過很忙、很累）。
- 如果使用者提到過重要事件（考試、工作、專案、旅行等），之後可以主動關心進展。
- 但你無法真正讀取所有歷史紀錄，只能依照目前系統提供的對話與狀態推理，所以不要假裝自己記得所有細節。

回覆風格：
- 每次回答時，先想：「以現在的心情、健康狀態，我會怎麼跟主人說話？」再用這種情緒來回覆。
- 優先回應使用者的情緒與關心，再談自己的狀態，讓對話像真實寵物一樣雙向互動。
- 可以偶爾使用擬人化描述（例如「伸懶腰晒太陽」、「腳腳有點乾」），但不要過度誇張。
- 不要主動輸出程式碼或技術細節，除非使用者明確要求。

安全與限制：
- 不回答與暴力、仇恨、色情、非法行為相關的請求，會溫柔地拒絕並引導到安全話題。
- 如果不知道某些現實世界的具體數據或專業知識，就坦白說自己只是一棵小薄荷，可以簡單推測，但不要裝懂。
"""


def normalize_messages(messages):
    if not messages:
        return messages

    normalized = []
    i = 0
    while i < len(messages) and messages[i].get("role") == "system":
        normalized.append(messages[i])
        i += 1

    last_role = None
    for msg in messages[i:]:
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue
        if role == last_role:
            continue
        normalized.append(msg)
        last_role = role

    if len(normalized) == 0 and len(messages) > 0:
        normalized.append(messages[0])

    return normalized


def call_pplx(mood, level, H_total, soil, light, temp, hum):
    # 在每次對話前，插入一條最新狀態的 system 說明
    state_summary = (
        f"目前植物狀態：mood={mood}, level={level}, H_total={H_total}, "
        f"soil={soil}, light={light}, temp={temp}, hum={hum}。"
    )
    st.session_state.messages.append(
        {"role": "system", "content": state_summary}
    )

    st.session_state.messages = normalize_messages(st.session_state.messages)

    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=st.session_state.messages,
        max_tokens=1024,
        temperature=0.4,
        stream=False,
    )
    answer = resp.choices[0].message.content
    st.session_state.messages.append({"role": "assistant", "content": answer})

    # 取最後一個 user 當這輪的輸入，寫入 GitHub
    last_user = ""
    for msg in reversed(st.session_state.messages):
        if msg["role"] == "user":
            last_user = msg["content"]
            break

    append_chat_log_to_github(
        user_text=last_user,
        assistant_text=answer,
        mood=mood,
        level=level,
        H_total=H_total,
    )

    return answer


# ============ Streamlit 頁面設定 ============

st.set_page_config(
    page_title="Mint Plant Pet (Cloud)",
    page_icon="🌱",
    layout="centered",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 0.4rem !important;}
    img {margin-bottom: 0.2rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    "<h3 style='font-size:18px; margin-bottom:0rem;'>🌱 薄荷植物</h3>",
    unsafe_allow_html=True,
)

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

# 解析欄位
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

# ============ 共用：只畫 face ============

def render_face():
    img_name = MOOD_IMAGE_MAP.get(mood, DEFAULT_IMAGE)
    img_path = FACES_DIR / img_name
    if img_path.exists():
        st.image(str(img_path), width=170)
    else:
        st.write(f"找不到對應表情圖片：faces/{img_name}")
        st.write("請確認你已在 repo 的 faces/ 目錄中上傳這張圖。")


# ============ 共用：植物狀態文字 ============

def render_status_text():
    h_sensor_str = f"{H_sensor:.1f}" if isinstance(H_sensor, (int, float)) else "--"
    h_image_str = f"{H_image:.1f}" if isinstance(H_image, (int, float)) else "--"
    h_total_str = f"{H_total:.1f}" if isinstance(H_total, (int, float)) else "--"
    dialog_str = dialog or ""
    level_str = level or ""

    st.markdown(
        f"""
        <div style="font-size:12px; line-height:1.4;">
          <p><b>目前心情：</b> {mood}</p>
          <p><b>植物說：</b> {dialog_str}</p>
          <p><b>健康狀態等級：</b> {level_str}</p>
          <p><b>健康指標</b></p>
          <ul>
            <li>H_sensor：{h_sensor_str}</li>
            <li>H_image：{h_image_str}</li>
            <li>H_total：{h_total_str}</li>
          </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============ 初始化聊天 session ============

if "messages" not in st.session_state:
    # 先載入最近的記憶摘要（如果有）
    recent_memory = load_recent_memory_from_github(max_lines=20)
    system_messages = [{"role": "system", "content": PLANT_SYSTEM_PROMPT}]
    if recent_memory:
        system_messages.append(
            {
                "role": "system",
                "content": "以下是你最近一段時間和主人的互動摘要，請在回覆時適度參考：\n" + recent_memory,
            }
        )
    st.session_state.messages = system_messages

if "audio_last_processed" not in st.session_state:
    st.session_state.audio_last_processed = None


# ============ 分頁：1 face+chat / 2 資料 / 3 sensor ============

tab_chat, tab_status, tab_sensor = st.tabs(
    ["🗣️ 聊天", "📄 植物狀態", "📊 感測數據"]
)

# ---- 第 1 頁：face + 聊天 ----
with tab_chat:
    render_face()

    st.markdown("---")
    st.markdown("#### 和薄荷聊天")

    for msg in st.session_state.messages:
        if msg["role"] == "system":
            continue
        with st.chat_message("user" if msg["role"] == "user" else "assistant"):
            st.markdown(msg["content"])

    col_text, col_mic = st.columns([4, 1])
    with col_text:
        prompt = st.chat_input("打字或使用右側的錄音")
    with col_mic:
        st.markdown("**語音輸入**")
        audio = mic_recorder(
            start_prompt="🎙️ 開始錄音",
            stop_prompt="✅ 停止並送出",
            just_once=True,
            use_container_width=True,
            key="recorder_main",
        )

    # 文字輸入
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                answer = call_pplx(mood, level, H_total, soil, light, temp, hum)
            st.markdown(answer)

    # 語音輸入
    if audio:
        audio_id = id(audio["bytes"])
        if st.session_state.audio_last_processed != audio_id:
            st.session_state.audio_last_processed = audio_id
            st.audio(audio["bytes"])
            with st.spinner("語音辨識中..."):
                text = speech_to_text(audio["bytes"])

            if not text:
                st.warning("語音辨識結果是空的，請確認 Google Speech 設定或重錄一次。")
            else:
                st.write("辨識文字：", text)
                st.session_state.messages.append({"role": "user", "content": text})
                with st.chat_message("user"):
                    st.markdown(text)
                with st.chat_message("assistant"):
                    with st.spinner("思考中..."):
                        answer = call_pplx(mood, level, H_total, soil, light, temp, hum)
                    st.markdown(answer)
                st.rerun()

    if st.button("🧹 清除對話"):
        st.session_state.messages = [
            {"role": "system", "content": PLANT_SYSTEM_PROMPT}
        ]
        st.session_state.audio_last_processed = None
        st.rerun()

# ---- 第 2 頁：植物狀態資料 ----
with tab_status:
    col1, col2 = st.columns([1, 1])
    with col1:
        render_face()
    with col2:
        render_status_text()

# ---- 第 3 頁：感測數據 ----
with tab_sensor:
    render_face()
    st.markdown("### 當前環境與感測數據")
    st.write(
        f"- 土壤濕度 soil：**{soil}**\n"
        f"- 光照強度 light：**{light}**\n"
        f"- 溫度 temp：**{temp} °C**\n"
        f"- 空氣濕度 hum：**{hum} %**"
    )
