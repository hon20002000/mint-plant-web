#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import json
import os
from datetime import datetime
from typing import Optional

import requests

# ===== GitHub 設定 =====
# 請先在系統環境變數設定 GITHUB_TOKEN，並給這個 repo 寫入權限
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_OWNER = "hon20002000"
GITHUB_REPO = "mint-plant-web"
GITHUB_PATH = "cloud_logs/plant_chat.jsonl"  # 存聊天紀錄的檔案路徑


def _get_github_file():
    """
    讀取 GitHub 上指定檔案的內容與 sha。
    回傳 (text, sha)；若檔案不存在，回傳 ("", None)。
    """
    if not GITHUB_TOKEN:
        return "", None

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        sha = data.get("sha")
        content_bytes = base64.b64decode(data.get("content", ""))
        text = content_bytes.decode("utf-8")
        return text, sha
    elif resp.status_code == 404:
        # 檔案不存在
        return "", None
    else:
        # 其它錯誤時，不阻塞主程式，直接回空
        return "", None


def _put_github_file(new_text: str, sha: Optional[str]):
    """
    把 new_text 以 base64 形式寫回 GitHub 指定檔案。
    如果 sha 為 None，代表建立新檔案；否則更新既有檔案。
    """
    if not GITHUB_TOKEN:
        return

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    ts_str = datetime.utcnow().isoformat()
    b64_content = base64.b64encode(new_text.encode("utf-8")).decode("utf-8")

    payload = {
        "message": f"append plant chat log {ts_str}",
        "content": b64_content,
    }
    if sha:
        payload["sha"] = sha

    requests.put(url, headers=headers, json=payload)


def append_chat_log_to_github(
    user_text: str,
    assistant_text: str,
    mood,
    level,
    H_total,
):
    """
    將一筆聊天紀錄附加到 GitHub 上的 JSON Lines 檔案。
    每行是一個 JSON object，包含：
    timestamp, mood, level, H_total, user, assistant
    """
    if not GITHUB_TOKEN:
        # 沒設 token 就直接跳過，不影響主程式
        return

    # 1. 先讀取目前檔案內容與 sha
    old_text, sha = _get_github_file()

    # 2. 準備新的一行 JSON
    ts_str = datetime.utcnow().isoformat()
    record = {
        "timestamp": ts_str,
        "mood": mood,
        "level": level,
        "H_total": H_total,
        "user": user_text,
        "assistant": assistant_text,
    }
    new_line = json.dumps(record, ensure_ascii=False)

    if old_text.strip():
        new_content = old_text.rstrip("\n") + "\n" + new_line + "\n"
    else:
        new_content = new_line + "\n"

    # 3. 寫回 GitHub
    _put_github_file(new_content, sha)


def load_recent_memory_from_github(max_lines: int = 20) -> str:
    """
    從 GitHub 的 plant_chat.jsonl 讀取最近 max_lines 筆對話，
    生成一段「薄荷仔對主人的印象摘要」字串。
    如果讀取或解析失敗，回傳空字串。
    """
    if not GITHUB_TOKEN:
        return ""

    text, _ = _get_github_file()
    if not text.strip():
        return ""

    # 拿最後 max_lines 行非空行
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""

    lines = lines[-max_lines:]

    try:
        records = [json.loads(ln) for ln in lines]
    except Exception:
        return ""

    moods = {}
    levels = {}
    user_snippets = []

    for r in records:
        m = r.get("mood")
        if m:
            moods[m] = moods.get(m, 0) + 1
        lv = r.get("level")
        if lv:
            levels[lv] = levels.get(lv, 0) + 1
        u = r.get("user") or ""
        if isinstance(u, str) and u.strip():
            user_snippets.append(u.strip()[:30])

    mood_str = ""
    if moods:
        top_moods = sorted(moods.items(), key=lambda x: x[1], reverse=True)[:2]
        mood_str = "、".join([f"{name}（約 {count} 次）" for name, count in top_moods])

    level_str = ""
    if levels:
        top_levels = sorted(levels.items(), key=lambda x: x[1], reverse=True)[:2]
        level_str = "、".join([f"{name}（約 {count} 次）" for name, count in top_levels])

    parts = []
    parts.append(f"這是我最近 {len(records)} 次和主人的對話印象：")

    if user_snippets:
        parts.append("主人常常提到這些事情或感受：")
        for s in user_snippets[-5:]:
            parts.append(f"- 「{s}...」")

    if mood_str:
        parts.append(f"在這段時間裡，我自己的心情多半是：{mood_str}。")
    if level_str:
        parts.append(f"健康狀態等級的變化大致是：{level_str}。")

    parts.append("未來我回覆主人時，會盡量記得這些感覺和話題。")

    return "\n".join(parts)
