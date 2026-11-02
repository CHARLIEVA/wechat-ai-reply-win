# -*- coding: utf-8 -*-
"""
wechat-ai-reply-win: AI auto-reply for WeChat 4.x on Windows (wxauto4 UI automation).
Windows 微信 4.x AI 自动回复（基于 wxauto4 界面自动化）。

Flow / 流程:
  poll sessions -> open chats with new messages -> trigger check (name / @me)
  -> dedup -> persona + shared facts + this chat's notes/memory + history -> AI -> reply (@ asker in groups)

Run / 运行:  start.bat   (or:  py -3.13 bot.py)

Reliability / 可靠性:
  - startup snapshot: messages that existed before start are marked seen, never replied to
    启动快照：启动前已有的消息/未读积压一律标记已读，不回复
  - heartbeat file (HEARTBEAT_FILE) written every poll, used by watchdog.ps1
    每轮轮询写心跳文件，供 watchdog.ps1 判断是否卡死
  - WeChat window kept small and in the background (wxbot/window.py)
    微信窗口保持小窗、放最底层、不抢前台
  - optional /btc /AAPL /600519 quote commands (STOCK_CMD_ENABLED, wxbot/stock.py)
"""
import os
import sys
import time

from wxbot import ai, kb, proactive, window
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

    window.install()
    wx = WeChat()
    window.to_back(resize=True)
    stock = None
    if C.STOCK_CMD_ENABLED:
        from wxbot import stock
    me = getattr(wx, "nickname", "") or ""
    seen = {}
    log(f"[start] WeChat={me} model={C.OPENAI_MODEL} triggers={'/'.join(C.TRIGGERS)} or @{me}. Ctrl+C to stop.")

    def is_trigger(text):
        return any(w and w in text for w in C.TRIGGERS) or (me and f"@{me}" in text)

    def mkey(m):
        return getattr(m, "id", None) or getattr(m, "hash", None) or id(m)

    def _send_msg(text, at=None):
        with window.sending():
            if at:
                wx.SendMsg(text, at=at)
            else:
                wx.SendMsg(text)

    def send(chat, text, at=None):
        wx.ChatWith(chat)
        time.sleep(0.5)
        _send_msg(text, at)

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
            # First time we open this chat. new_count<=0 means a pre-start backlog: mark ALL seen
            # and reply to nothing. Otherwise only the last n messages count as new.
            # 首次打开该会话：new_count<=0 表示启动前积压，全部标记已读、不回复；否则只把最后 n 条当新消息。
            n = int(new_count or 0)
            if n <= 0:
                seen[name] = {mkey(m) for m in msgs}
                log(f"[start] seed chat={name} msgs={len(msgs)} (backlog ignored, no reply)")
                return
            s = seen[name] = {mkey(m) for m in msgs[:-n]}
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
            if stock and stock.parse(text) is not None:
                sr = stock.handle(name, text)
                if sr:
                    _send_msg(sr)
                    log(f"[stock] {name}: {text[:20]}")
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
            _send_msg(reply, sender if (is_group and sender != name) else None)
            log(f"[reply] {name}: {reply[:60]}")
            try:
                kb.maybe_update_memory(name, ai.chat)
            except Exception as e:
                log(f"[memory] [{name}] error {e}")

    # Startup snapshot of session previews: anything already there before start is old.
    # 启动时记录会话预览快照：启动前就有的内容都算旧消息。
    snap = {}
    try:
        for sess in wx.GetSession():
            snap[sess.name] = (getattr(sess, "time", ""), getattr(sess, "content", ""))
        log(f"[start] session snapshot n={len(snap)} (pre-start messages will not be replied to)")
    except Exception as e:
        log(f"[start] session snapshot failed: {e}")

    def heartbeat():
        try:
            os.makedirs(os.path.dirname(C.HEARTBEAT_FILE), exist_ok=True)
            with open(C.HEARTBEAT_FILE, "w") as f:
                f.write(str(int(time.time())))
        except OSError:
            pass

    while True:
        heartbeat()
        try:
            for sess in wx.GetSession():
                cnt = getattr(sess, "new_count", 0) or 0
                sig = (getattr(sess, "time", ""), getattr(sess, "content", ""))
                prev = snap.get(sess.name)
                snap[sess.name] = sig
                changed = prev is not None and prev != sig
                isnew = bool(getattr(sess, "isnew", False) or cnt)
                if isnew and not changed and sess.name not in seen:
                    # unread badge with no new preview = backlog from before start: drain, don't reply
                    # 预览没变的未读角标 = 启动前积压：只标记已读，不回复
                    handle(sess.name, 0)
                elif isnew or changed:
                    handle(sess.name, cnt or 1)
                else:
                    continue
                window.to_back()
            proactive.tick(send, ai.chat)
        except KeyboardInterrupt:
            break
        except Exception as e:
            log("[error]", e)
        time.sleep(C.POLL_SEC)


if __name__ == "__main__":
    main()
