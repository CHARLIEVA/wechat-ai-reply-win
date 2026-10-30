# -*- coding: utf-8 -*-
"""Settings from .env + persona loading.  从 .env 读取配置、加载人设。"""
import os
import re

from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(ROOT, ".env"))


def _env(k, d=""):
    return (os.environ.get(k) or d).strip()


def _bool(k, d):
    return _env(k, str(d)).lower() in ("1", "true", "yes", "on")


def _num(k, d):
    try:
        return float(_env(k, str(d)))
    except ValueError:
        return d


def _list(k):
    return [w.strip() for w in _env(k).replace("，", ",").split(",") if w.strip()]


LANGUAGE = "en" if _env("LANGUAGE", "zh-CN").lower().startswith("en") else "zh-CN"
TIMEZONE_NOTE = "Times use the PC's local clock. 时间使用本机时钟。"

# AI (any OpenAI-compatible API) / AI 接口
OPENAI_API_KEY = _env("OPENAI_API_KEY")
OPENAI_BASE_URL = _env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TIMEOUT = _num("OPENAI_TIMEOUT_SEC", 90)

# Identity & triggers / 身份与触发
BOT_NAME = _env("BOT_NAME", "Nova" if LANGUAGE == "en" else "小星")
TRIGGERS = [BOT_NAME] + _list("BOT_ALIASES")

# Scope / 回复范围
REPLY_IN_GROUPS = _bool("REPLY_IN_GROUPS", True)
REPLY_IN_PRIVATE = _bool("REPLY_IN_PRIVATE", False)
PRIVATE_REQUIRE_TRIGGER = _bool("PRIVATE_REQUIRE_TRIGGER", True)
CHAT_ALLOWLIST = _list("CHAT_ALLOWLIST")
CHAT_BLOCKLIST = _list("CHAT_BLOCKLIST")
CONTEXT_MESSAGES = int(_num("CONTEXT_MESSAGES", 10))
MAX_REPLY_CHARS = int(_num("MAX_REPLY_CHARS", 300))
DEDUP_HOURS = _num("DEDUP_HOURS", 12)
POLL_SEC = _num("POLL_SEC", 2)

# Memory / 记忆
MEMORY_ENABLED = _bool("MEMORY_ENABLED", True)
MEMORY_EVERY_N = int(_num("MEMORY_EVERY_N", 10))

# Proactive / 主动聊天
PROACTIVE_ENABLED = _bool("PROACTIVE_ENABLED", False)
PROACTIVE_CHATS = _list("PROACTIVE_CHATS")
PROACTIVE_HOURS = _env("PROACTIVE_HOURS", "09:00-22:30")
PROACTIVE_QUIET_MIN = _num("PROACTIVE_QUIET_MIN", 45)
PROACTIVE_COOLDOWN_MIN = _num("PROACTIVE_COOLDOWN_MIN", 180)
PROACTIVE_MAX_PER_DAY = int(_num("PROACTIVE_MAX_PER_DAY", 3))
PROACTIVE_PROB = _num("PROACTIVE_PROB", 0.3)
PROACTIVE_CHECK_MIN = _num("PROACTIVE_CHECK_MIN", 10)

KB_DIR = os.path.join(ROOT, _env("KB_DIR", "kb"))
LOG_FILE = os.path.join(ROOT, _env("LOG_FILE", "logs/bot.log"))


def persona_file():
    p = _env("PERSONA_FILE") or os.path.join("persona", "persona.en.md" if LANGUAGE == "en" else "persona.zh-CN.md")
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def load_persona():
    """Re-read on every call, so edits apply without restart. 每次调用都重新读取，改完无需重启。"""
    try:
        with open(persona_file(), encoding="utf-8") as f:
            raw = f.read()
    except OSError:
        raw = f'You are "{BOT_NAME}", a member of a WeChat group. Reply briefly and plainly.'
    return re.sub(r"<!--[\s\S]*?-->", "", raw).strip().replace("{{BOT_NAME}}", BOT_NAME)


def chat_allowed(name):
    if name in CHAT_BLOCKLIST:
        return False
    return not CHAT_ALLOWLIST or name in CHAT_ALLOWLIST
