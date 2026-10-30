# -*- coding: utf-8 -*-
"""Check .env and persona without touching WeChat; --ping also calls the AI.
不连接微信，检查 .env 和人设；加 --ping 会实际调用一次 AI。"""
import os
import sys

from wxbot import config as C

ok = True


def line(good, msg):
    global ok
    print(("[ OK ] " if good else "[FAIL] ") + msg)
    ok = ok and good


line(sys.version_info >= (3, 9), f"Python {sys.version.split()[0]} (3.13 x64 recommended / 建议 3.13 x64)")
line(os.path.exists(os.path.join(C.ROOT, ".env")), ".env exists / .env 文件存在")
line(bool(C.OPENAI_API_KEY), "OPENAI_API_KEY set / 已填写 OPENAI_API_KEY")
line(C.OPENAI_BASE_URL.startswith("http"), f"OPENAI_BASE_URL = {C.OPENAI_BASE_URL}")
line(os.path.exists(C.persona_file()), f"persona / 人设: {C.persona_file()}")
print(f"       LANGUAGE={C.LANGUAGE} BOT_NAME={C.BOT_NAME} MODEL={C.OPENAI_MODEL}")
print(f"       groups={C.REPLY_IN_GROUPS} private={C.REPLY_IN_PRIVATE} memory={C.MEMORY_ENABLED} proactive={C.PROACTIVE_ENABLED}")
print("\n--- persona preview / 人设预览 ---\n" + C.load_persona()[:160] + " ...\n")
if "--ping" in sys.argv and ok:
    from wxbot import ai
    try:
        print("[ OK ] AI: " + ai.chat([{"role": "user", "content": "ping"}], max_tokens=20))
    except Exception as e:
        line(False, f"AI call failed / AI 调用失败: {e}")
sys.exit(0 if ok else 1)
