# -*- coding: utf-8 -*-
"""Minimal OpenAI-compatible chat client.  极简 OpenAI 兼容接口客户端。"""
import time

import httpx

from . import config as C


def chat(messages, max_tokens=800, retries=3):
    if not C.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing / 未设置 OPENAI_API_KEY")
    last = None
    for i in range(retries):
        try:
            r = httpx.post(
                f"{C.OPENAI_BASE_URL}/chat/completions",
                timeout=C.OPENAI_TIMEOUT,
                headers={"Authorization": f"Bearer {C.OPENAI_API_KEY}"},
                json={"model": C.OPENAI_MODEL, "messages": messages, "max_tokens": max_tokens},
            )
            if r.status_code == 200:
                return (r.json()["choices"][0]["message"]["content"] or "").strip()
            last = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:  # network errors / 网络错误
            last = str(e)
        print(f"[ai] retry {i + 1}/{retries}: {last}")
        time.sleep(3)
    raise RuntimeError(last)
