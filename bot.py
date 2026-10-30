# -*- coding: utf-8 -*-
"""
wechat-ai-reply-win: AI auto-reply for WeChat 4.x on Windows (wxauto4 UI automation).
Windows 微信 4.x AI 自动回复（基于 wxauto4 界面自动化）。

Flow / 流程:
  poll sessions -> open chats with new messages -> trigger check (name / @me)
  -> dedup -> persona + shared facts + this chat's notes/memory + history -> AI -> reply (@ asker in groups)

Run / 运行:  start.bat   (or:  py -3.13 bot.py)
"""
import os
import sys
import time

from wxbot import ai, kb, proactive
from wxbot import config as C


def log(*a):
    line = time.strftime("[%Y-%m-%d %H:%M:%S] ") + " ".join(str(x) for x in a)
    if C.OPENAI_API_KEY:
        line = line.replace(C.OPENAI_API_KEY, "<redacted>")
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(C.LOG_FILE), exist_ok=True)
        with open(C.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def build_reply(chat, sender, text, is_group):
    sys_prompt = C.load_persona()
    bg = kb.background(chat)
    if bg:
        sys_prompt += "\n\n" + bg
    if is_group:
        sys_prompt += f"\n\n[Current group / 当前群] {chat}"
    msgs = [{"role": "system", "content": sys_prompt}] + kb.history(chat, C.CONTEXT_MESSAGES)
    msgs.append({"role": "user", "content": f"{sender}: {text}"})
    out = ai.chat(msgs)
    return out.split("\n\n")[0].strip()[: C.MAX_REPLY_CHARS]


def main():
    if not C.OPENAI_API_KEY:
        sys.exit("[ERROR] OPENAI_API_KEY is not set in .env / .env 里没有填写 OPENAI_API_KEY")
    from wxauto4 import WeChat  # Windows only / 仅 Windows

    wx = WeChat()
    me = getattr(wx, "nickname", "") or ""
    seen = {}
    log(f"[start] WeChat={me} model={C.OPENAI_MODEL} triggers={'/'.join(C.TRIGGERS)} or @{me}. Ctrl+C to stop.")

    def is_trigger(text):
        return any(w and w in text for w in C.TRIGGERS) or (me and f"@{me}" in text)

    def mkey(m):
        return getattr(m, "id", None) or getattr(m, "hash", None) or id(m)

    def send(chat, text, at=None):
        wx.ChatWith(chat)
        time.sleep(0.5)
        if at:
            wx.SendMsg(text, at=at)
        else:
            wx.SendMsg(text)

    def handle(name, new_count):
        if not C.chat_allowed(name):
            return
        wx.ChatWith(name)
        time.sleep(0.5)
        try:
            is_group = (wx.ChatInfo() or {}).get("chat_type") == "group"
        except Exception:
            is_group = False
        msgs = wx.GetAllMessage()
        s = seen.get(name)
        if s is None:
            s = seen[name] = {mkey(m) for m in msgs[: -max(int(new_count or 1), 1)]}
        fresh = [m for m in msgs if mkey(m) not in s]
        s.update(mkey(m) for m in fresh)
        if any(getattr(m, "attr", "") == "friend" for m in fresh):
            proactive.note(name)
        if (is_group and not C.REPLY_IN_GROUPS) or (not is_group and not C.REPLY_IN_PRIVATE):
            return
        latest = {}  # only the latest trigger per sender in a burst / 连发时每人只答最新一条
        for m in fresh:
            text = (getattr(m, "content", "") or "").strip()
            if getattr(m, "attr", "") != "friend" or not text:
                continue
            if (is_group or C.PRIVATE_REQUIRE_TRIGGER) and not is_trigger(text):
                continue
            latest[getattr(m, "sender", "") or name] = text
        for sender, text in latest.items():
            k = kb.dkey(name, sender, text)
            if kb.already_handled(k):
                log(f"[dedup] skip {name} | {sender}")
                continue
            kb.mark_handled(k)
            log(f"[message] {'group' if is_group else 'private'} {name} | {sender}: {text[:60]}")
            reply = build_reply(name, sender, text, is_group)
            if not reply:
                continue
            kb.save(name, sender, text, reply, is_group)
            if is_group and sender != name:
                wx.SendMsg(reply, at=sender)
            else:
                wx.SendMsg(reply)
            log(f"[reply] {name}: {reply[:60]}")
            try:
                kb.maybe_update_memory(name, ai.chat)
            except Exception as e:
                log(f"[memory] [{name}] error {e}")

    while True:
        try:
            for sess in wx.GetSession():
                cnt = getattr(sess, "new_count", 0) or 0
                if getattr(sess, "isnew", False) or cnt:
                    handle(sess.name, cnt)
            proactive.tick(send, ai.chat)
        except KeyboardInterrupt:
            break
        except Exception as e:
            log("[error]", e)
        time.sleep(C.POLL_SEC)


if __name__ == "__main__":
    main()
