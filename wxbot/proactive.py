# -*- coding: utf-8 -*-
"""
Proactive chat (off by default, experimental).  主动聊天（默认关闭，实验性）

Only for group names listed in PROACTIVE_CHATS. A group gets one short line only when ALL hold:
仅对 PROACTIVE_CHATS 里列出的群生效，且同时满足以下条件才会说一句：
  within PROACTIVE_HOURS / 在活跃时段内
  someone spoke in the last 24h / 最近 24 小时有人说过话
  quiet for PROACTIVE_QUIET_MIN / 已安静足够久
  cooldown passed and daily cap not reached / 冷却已过且未达每日上限
  random() < PROACTIVE_PROB / 掷骰子通过
"""
import json
import os
import random
import time
from datetime import datetime

from . import config as C
from . import kb

STATE = os.path.join(C.KB_DIR, "proactive.json")
TASK = {
    "zh-CN": "群里已经安静一阵子了，你要主动打破沉默。只说一句简短自然的话，像普通群友随口一说：可以接着最近的话题，或问个轻松的问题。不要打招呼，不要说自己是 AI，不要 @ 任何人，不要夸人，直接输出这句话。",
    "en": "The group has been quiet for a while. Break the silence with ONE short, natural line, like a normal member: follow up on a recent topic or ask a light question. No greetings, don't say you are an AI, don't @ anyone, no flattery. Output only that line.",
}


def _load():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


_st = _load()
_last_check = 0.0


def _save():
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(_st, f, ensure_ascii=False, indent=1)


def _s(chat):
    return _st.setdefault(chat, {"last_msg": 0, "last_human": 0, "last_pro": 0, "day": "", "count": 0})


def note(chat, human=True):
    """Call whenever a chat shows new messages. 会话有新消息时调用"""
    s = _s(chat)
    s["last_msg"] = time.time()
    if human:
        s["last_human"] = s["last_msg"]
    _save()


def _in_hours():
    a, b = C.PROACTIVE_HOURS.split("-")
    now = datetime.now().strftime("%H:%M")
    return a <= now <= b


def tick(send, ask):
    """Called from the main loop; send(chat, text) does the UI work. 由主循环调用"""
    global _last_check
    if not C.PROACTIVE_ENABLED or not C.PROACTIVE_CHATS:
        return
    if time.time() - _last_check < C.PROACTIVE_CHECK_MIN * 60 or not _in_hours():
        return
    _last_check = time.time()
    today = datetime.now().strftime("%Y-%m-%d")
    now = time.time()
    for chat in C.PROACTIVE_CHATS:
        s = _s(chat)
        if s["day"] != today:
            s["day"], s["count"] = today, 0
        if not s["last_human"] or now - s["last_human"] > 24 * 3600:
            continue
        if now - s["last_msg"] < C.PROACTIVE_QUIET_MIN * 60 or now - s["last_pro"] < C.PROACTIVE_COOLDOWN_MIN * 60:
            continue
        if s["count"] >= C.PROACTIVE_MAX_PER_DAY or random.random() >= C.PROACTIVE_PROB:
            continue
        sys_prompt = C.load_persona() + "\n\n" + kb.background(chat) + "\n\n" + TASK[C.LANGUAGE]
        msgs = [{"role": "system", "content": sys_prompt}] + kb.history(chat, 6)
        if len(msgs) == 1:
            msgs.append({"role": "user", "content": "-"})
        try:
            line = ask(msgs, max_tokens=200).strip().strip('"“”\'').split("\n")[0][:120]
            if line:
                send(chat, line)
                s["last_pro"] = s["last_msg"] = time.time()
                s["count"] += 1
                print(f"[proactive] [{chat}] sent ({s['count']}/{C.PROACTIVE_MAX_PER_DAY} today)")
        except Exception as e:
            print(f"[proactive] [{chat}] error {e}")
    _save()
