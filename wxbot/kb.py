# -*- coding: utf-8 -*-
"""
Local knowledge base, per-chat isolated.  本地知识库（按会话隔离）

kb/shared.md                    facts every chat may use (hand-written, hot-reloaded)
                                所有会话共用的固定事实（手写，热加载）
kb/chats/<chat>/chat.jsonl      this chat's Q&A history       本会话问答记录
kb/chats/<chat>/knowledge.md    hand-written notes for this chat (hot-reloaded)
                                只属于本会话的手写知识（热加载）
kb/chats/<chat>/memory.md       AI-summarized long-term memory  AI 整理的长期记忆
kb/handled.jsonl                dedup records                 去重记录
kb/proactive.json               proactive-chat state          主动聊天状态

A chat never sees another chat's files. 一个会话永远读不到其他会话的文件。
"""
import hashlib
import json
import os
import re
import time
from datetime import datetime

from . import config as C

CHATS = os.path.join(C.KB_DIR, "chats")
SHARED = os.path.join(C.KB_DIR, "shared.md")
HANDLED = os.path.join(C.KB_DIR, "handled.jsonl")
os.makedirs(CHATS, exist_ok=True)


def scrub(t):
    """Mask obviously sensitive data before storing. 落盘前遮掉敏感信息"""
    t = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "[key]", t or "")
    t = re.sub(r"\b\d{17}[\dXx]\b", "[id-number]", t)
    t = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[phone]", t)
    return re.sub(r"\b\d{16,19}\b", "[card]", t)


def chat_dir(chat):
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", chat or "unknown").strip(" .")[:80] or "unknown"
    d = os.path.join(CHATS, name)
    os.makedirs(d, exist_ok=True)
    return d


def read_tail(path, n):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()[-n:]
    except OSError:
        return ""


def rows(chat):
    out = []
    try:
        with open(os.path.join(chat_dir(chat), "chat.jsonl"), encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    return out


def history(chat, n):
    """Recent exchanges of THIS chat as chat messages. 本会话近期问答"""
    msgs = []
    for r in rows(chat)[-n:]:
        if r.get("user_text"):
            msgs.append({"role": "user", "content": f"{r.get('sender', '')}: {r['user_text']}"})
        if r.get("reply"):
            msgs.append({"role": "assistant", "content": r["reply"]})
    return msgs


def background(chat):
    """shared.md + this chat's knowledge.md + memory.md, read fresh each time. 每次都从磁盘读取"""
    d = chat_dir(chat)
    parts = []
    for title, path, n in (("Shared facts / 共享事实", SHARED, 1500),
                           ("Notes for this chat / 本会话知识", os.path.join(d, "knowledge.md"), 2000),
                           ("Long-term memory of this chat / 本会话长期记忆", os.path.join(d, "memory.md"), 2000)):
        t = read_tail(path, n).strip()
        if t:
            parts.append(f"[{title}]\n{t}")
    return "\n\n".join(parts)


def save(chat, sender, text, reply, is_group):
    e = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "chat": chat, "is_group": bool(is_group),
         "sender": sender, "user_text": scrub(text), "reply": scrub(reply)}
    with open(os.path.join(chat_dir(chat), "chat.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")


# ---- on-disk dedup / 落盘去重 ----
_handled = {}
try:
    with open(HANDLED, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
                _handled[e["k"]] = e.get("t", 0)
            except Exception:
                pass
except OSError:
    pass


def dkey(chat, sender, text):
    return hashlib.sha1(f"{chat}\x1f{sender}\x1f{text}".encode("utf-8")).hexdigest()


def already_handled(k):
    t = _handled.get(k)
    return t is not None and time.time() - t < C.DEDUP_HOURS * 3600


def mark_handled(k):
    _handled[k] = time.time()
    with open(HANDLED, "a", encoding="utf-8") as f:
        f.write(json.dumps({"k": k, "t": _handled[k]}) + "\n")


# ---- long-term memory summarization / 长期记忆整理 ----
MEM_PROMPT = {
    "zh-CN": ("你为微信助手“{name}”维护某个会话的长期记忆。把【已有记忆】和【新对话】合并成更新后的记忆，"
              "Markdown，简体中文，不超过 1500 字。分节：成员与称呼、偏好与兴趣、进行中的话题、约定与日期（写绝对日期）、事实。"
              "去重，新旧矛盾以新为准，删除过期内容，每条一行。严禁记录手机号、身份证号、住址、密码、验证码、银行卡、密钥等敏感信息。"
              "只记真正说过的内容，不要编造。只输出正文。"),
    "en": ("You maintain long-term memory of one WeChat chat for the assistant \"{name}\". Merge [Existing memory] and "
           "[New exchanges] into an updated memory in Markdown, at most 1500 characters. Sections: members and names, "
           "preferences, ongoing topics, plans and dates (absolute dates), facts. Dedupe, newer wins, drop expired items, "
           "one line per item. Never record phone numbers, ID numbers, addresses, passwords, codes, bank cards or keys. "
           "Only record what was actually said. Output only the content."),
}


def maybe_update_memory(chat, ask):
    """Every MEMORY_EVERY_N new exchanges, summarize into memory.md. 每新增 N 条问答整理一次"""
    if not C.MEMORY_ENABLED:
        return
    d = chat_dir(chat)
    state_path = os.path.join(d, "memory-state.json")
    try:
        with open(state_path, encoding="utf-8") as f:
            done = json.load(f).get("done", 0)
    except (OSError, ValueError):
        done = 0
    all_rows = rows(chat)
    new = all_rows[done:]
    if len(new) < C.MEMORY_EVERY_N:
        return
    lines = "\n".join(f"[{r.get('ts')}] {r.get('sender')}: {r.get('user_text')}\n{C.BOT_NAME}: {r.get('reply')}" for r in new[-200:])
    old = read_tail(os.path.join(d, "memory.md"), 3000) or "-"
    out = ask([{"role": "system", "content": MEM_PROMPT[C.LANGUAGE].format(name=C.BOT_NAME)},
               {"role": "user", "content": f"Chat / 会话: {chat}\n\n[Existing memory]\n{old}\n\n[New exchanges]\n{lines[-10000:]}"}],
              max_tokens=2000)
    if out and len(out) > 20:
        with open(os.path.join(d, "memory.md"), "w", encoding="utf-8") as f:
            f.write(scrub(out) + "\n")
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump({"done": len(all_rows)}, f)
    print(f"[memory] [{chat}] updated from {len(new)} exchanges")
