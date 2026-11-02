# -*- coding: utf-8 -*-
"""微信斜杠行情命令：/btc  /AAPL  /600519  /00700  /英伟达  /苹果  /贵州茅台

数据源：
  加密货币（BTC/ETH 等）：Binance 公共行情 data-api.binance.vision（部分地区 api.binance.com 返回 451，作为备用），
      1 分钟 K 线取最近 16 根：现价 = 最新收盘价，15 分钟前 = 15 根之前那根 K 线的收盘价。
  股票：
      1) 名称/代码解析：先查 stock_aliases.json（美股中文别名，热加载），再腾讯 smartbox
      2) 现价：美股在配置了 FINNHUB_API_KEY 且 Finnhub 可达时用 Finnhub /quote，否则用腾讯 qt.gtimg.cn
      3) 15 分钟涨跌：腾讯分时（逐分钟价格）取最新价 vs 15 分钟前的价格。
         Finnhub 免费版没有 K 线接口，算不了 15 分钟涨跌。
         已收盘时，给出的是“收盘前最后 15 分钟”的涨跌，并会注明。
         没有分时数据时（例如美股盘前），只显示当日涨跌。
密钥：FINNHUB_API_KEY（写在 .env 或环境变量里，可选）。不会写进日志。
别名：STOCK_ALIAS_FILE（默认 stock_aliases.json，可选），改完自动热加载，不必重启机器人。
所有请求都用 trust_env=False，不继承系统 HTTP(S)_PROXY / ALL_PROXY（继承代理曾导致 Binance 超时）。
如确需代理访问 Finnhub，设置 FINNHUB_PROXY。
"""
import os, re, time, json, httpx

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ALIAS_FILE = os.path.join(ROOT, os.environ.get("STOCK_ALIAS_FILE", "stock_aliases.json"))
FINNHUB_PROXY = os.environ.get("FINNHUB_PROXY", "").strip() or None
COOLDOWN_SEC = float(os.environ.get("STOCK_CMD_COOLDOWN", "10"))

CRYPTO = {"btc": "BTC", "比特币": "BTC", "大饼": "BTC", "eth": "ETH", "以太坊": "ETH", "以太": "ETH",
          "sol": "SOL", "bnb": "BNB", "doge": "DOGE", "狗狗币": "DOGE", "xrp": "XRP", "ada": "ADA",
          "ton": "TON", "trx": "TRX", "ltc": "LTC", "link": "LINK", "avax": "AVAX", "pepe": "PEPE"}
BINANCE_HOSTS = ["https://data-api.binance.vision", "https://api.binance.com"]

_cool = {}
_finnhub_down_until = 0.0
_alias_cache = {"mtime": None, "map": {}}


def _finnhub_key():
    return os.environ.get("FINNHUB_API_KEY", "").strip()


def _load_aliases():
    """热加载 stock_aliases.json：文件 mtime 变化时重读。键忽略大小写。"""
    try:
        mt = os.path.getmtime(ALIAS_FILE)
    except OSError:
        _alias_cache["mtime"] = None
        _alias_cache["map"] = {}
        return {}
    if _alias_cache["mtime"] == mt:
        return _alias_cache["map"]
    try:
        raw = json.load(open(ALIAS_FILE, encoding="utf-8-sig"))
    except Exception as e:
        print(f"[stock] aliases load fail: {type(e).__name__}")
        return _alias_cache["map"]
    m = {}
    for k, v in raw.items():
        if not isinstance(k, str) or k.startswith("_") or not isinstance(v, str):
            continue
        ticker = v.strip().upper()
        if not ticker or not re.fullmatch(r"[A-Z0-9.\-]+", ticker):
            continue
        m[k.strip()] = ticker
        m[k.strip().lower()] = ticker
    _alias_cache["mtime"] = mt
    _alias_cache["map"] = m
    print(f"[stock] aliases loaded {len(m)} keys from stock_aliases.json")
    return m


def parse(text):
    """返回 /后面的查询词；不是行情命令返回 None。"""
    t = (text or "").strip()
    if not t.startswith("/") and not t.startswith("／"):
        return None
    q = t[1:].strip().split()[0] if t[1:].strip() else ""
    if not q or len(q) > 20 or "/" in q:
        return None
    if not re.fullmatch(r"[A-Za-z0-9.\-\u4e00-\u9fff]+", q):
        return None
    return q


def _fmt(x):
    if x is None:
        return "-"
    a = abs(x)
    if a >= 1000:
        return f"{x:,.2f}"
    if a >= 1:
        return f"{x:.2f}"
    return f"{x:.6g}"


def _chg(cur, old):
    if cur is None or not old:
        return None
    d = cur - old
    ds = f"{d:,.2f}" if abs(old) >= 1 else f"{d:.6g}"
    return f"{'+' if d >= 0 else ''}{ds}（{'+' if d >= 0 else ''}{d / old * 100:.2f}%）"


# ---------------- crypto ----------------
def _binance_klines(host, pair, interval, limit):
    """Fetch klines from one host; trust_env=False to avoid ALL_PROXY timeouts/451."""
    r = httpx.get(
        f"{host}/api/v3/klines",
        params={"symbol": pair, "interval": interval, "limit": limit},
        timeout=8,
        trust_env=False,
    )
    r.raise_for_status()
    k = r.json()
    if not isinstance(k, list) or len(k) < limit:
        got = len(k) if isinstance(k, list) else type(k)
        raise RuntimeError(f"klines too short interval={interval} got={got}")
    return k

def crypto(sym):
    """现价 + 15分钟 / 4小时 / 1日 涨跌（滚动窗口，与 15 分钟同款 _chg 格式）。

    15分钟：1m K 线 16 根（现价 vs 15 分钟前收盘）
    4小时：1h K 线取第 -5 根收盘（约 4 小时前）
    1日：1h K 线取第 -25 根收盘（约 24 小时前）
    """
    pair = sym + "USDT"
    last_err = None
    for h in BINANCE_HOSTS:
        try:
            k1m = _binance_klines(h, pair, "1m", 16)
            k1h = _binance_klines(h, pair, "1h", 25)
            cur = float(k1m[-1][4])
            old_15m = float(k1m[-16][4])
            old_4h = float(k1h[-5][4])
            old_1d = float(k1h[-25][4])
            ch15 = _chg(cur, old_15m) or "-"
            ch4h = _chg(cur, old_4h) or "-"
            ch1d = _chg(cur, old_1d) or "-"
            nl = chr(10)
            body = (
                f"{sym}/USDT（Binance）{nl}"
                f"现价：{_fmt(cur)} USDT{nl}"
                f"15分钟：{ch15}{nl}"
                f"4小时：{ch4h}{nl}"
                f"1日：{ch1d}"
            )
            return body, "binance"
        except Exception as e:
            last_err = e
    raise RuntimeError(f"binance failed: {last_err}")


# ---------------- stocks ----------------
def _alias_us(q):
    """别名命中 → (qt_code, minute_code, display_name) 或 None。只映射美股。"""
    m = _load_aliases()
    ticker = m.get(q) or m.get(q.lower())
    if not ticker:
        return None
    # 腾讯美股分时常见后缀 .OQ（纳斯达克）/ .N（纽交所）；先试 .OQ，报价用 usTICKER
    return "us" + ticker.replace(".", ""), "us" + ticker + ("" if "." in ticker else ".OQ"), q


def _resolve(q):
    """-> (qt_code, minute_code, name)  例：('sh600519','sh600519','贵州茅台') ('usAAPL','usAAPL.OQ','苹果')"""
    hit = _alias_us(q)
    if hit:
        return hit
    if re.fullmatch(r"\d{6}", q):
        mk = "sh" if q[0] in "569" else ("bj" if q[0] in "48" else "sz")
        return mk + q, mk + q, None
    if re.fullmatch(r"\d{5}", q):
        return "hk" + q, "hk" + q, None
    r = httpx.get("https://smartbox.gtimg.cn/s3/", params={"v": "2", "q": q, "t": "all"}, timeout=8, trust_env=False)
    m = re.search(r'v_hint="(.*)"', r.text)
    if not m or not m.group(1) or m.group(1) == "N":
        return None
    items = [x.split("~") for x in m.group(1).split("^")]
    items = [x for x in items if len(x) >= 5 and x[0] in ("sh", "sz", "bj", "hk", "us")]
    if not items:
        return None
    ql = q.lower()

    def score(x):
        mk, code, name, typ = x[0], x[1], json.loads(f'"{x[2]}"'), x[4]
        s = 0
        if code.split(".")[0].lower() == ql or name == q:
            s -= 100
        if typ.startswith("GP"):
            s -= 10
        if "ETF" in typ.upper() or "ETF" in name.upper():
            s += 5
        return s
    best = sorted(items, key=score)[0]
    if re.fullmatch(r"[A-Za-z.\-]+", q) and best[1].split(".")[0].lower() != ql:
        return None  # 纯英文只认精确代码，避免 /help 之类被模糊匹配成股票
    mk, code, name = best[:3]
    name = json.loads(f'"{name}"')
    if mk == "us":
        base = code.split(".")[0].upper()
        return "us" + base, "us" + code.upper(), name
    return mk + code, mk + code, name


def _tencent_quote(qt_code):
    r = httpx.get(f"https://qt.gtimg.cn/q={qt_code}", timeout=8, trust_env=False)
    r.encoding = "gbk"
    m = re.search(r'="(.*)"', r.text)
    if not m or not m.group(1):
        return None
    f = m.group(1).split("~")
    if len(f) < 33 or not f[3]:
        return None
    cur_txt = f[35] if qt_code.startswith("us") and len(f) > 35 and f[35] else ("HKD" if qt_code.startswith("hk") else "CNY")
    return {"name": f[1], "price": float(f[3]), "prev": float(f[4] or 0) or None,
            "time": f[30], "cur": cur_txt}


def _finnhub_quote(sym):
    global _finnhub_down_until
    key = _finnhub_key()
    if not key or time.time() < _finnhub_down_until:
        return None
    try:
        with httpx.Client(proxy=FINNHUB_PROXY, timeout=5, trust_env=False) as c:
            r = c.get("https://finnhub.io/api/v1/quote", params={"symbol": sym}, headers={"X-Finnhub-Token": key})
        if r.status_code != 200:
            print(f"[stock] finnhub http {r.status_code}")
            return None
        j = r.json()
        if not j.get("c"):
            return None
        return {"price": float(j["c"]), "prev": float(j.get("pc") or 0) or None}
    except Exception as e:
        _finnhub_down_until = time.time() + 600
        print(f"[stock] finnhub unreachable: {type(e).__name__}")
        return None


def _minute_15(minute_code):
    """-> (last_price, price_15m_ago, last_bar 'HHMM', bar_date) 或 None"""
    r = httpx.get("https://web.ifzq.gtimg.cn/appstock/app/minute/query", params={"code": minute_code}, timeout=8, trust_env=False)
    d = r.json().get("data", {}).get(minute_code, {}).get("data", {})
    rows = [x.split() for x in d.get("data", []) if len(x.split()) >= 2]
    if minute_code[:2] in ("sh", "sz", "bj"):
        rows = [x for x in rows if x[0] <= "1500"]
    if len(rows) < 16:
        return None
    return float(rows[-1][1]), float(rows[-16][1]), rows[-1][0], d.get("date", "")


def stock(q):
    res = _resolve(q)
    if not res:
        return None, "notfound"
    qt_code, minute_code, name = res
    # Finnhub 美股 ticker：usNVDA → NVDA；usBRKB → BRK.B（别名里带点）
    fh_sym = None
    if qt_code.startswith("us"):
        raw = qt_code[2:]
        aliases = _load_aliases()
        mapped = aliases.get(q) or aliases.get(q.lower())
        fh_sym = mapped if mapped else raw
    tq = _tencent_quote(qt_code)
    if tq is None and qt_code.startswith("us") and "." not in qt_code[2:]:
        # 别名路径的 minute_code 带 .OQ，报价码有时也要带后缀才有数据
        for suffix in (".OQ", ".N", ".A", ".B"):
            tq2 = _tencent_quote(qt_code + suffix)
            if tq2:
                tq = tq2
                minute_code = qt_code + suffix
                break
    src = "腾讯行情"
    price = tq["price"] if tq else None
    prev = tq["prev"] if tq else None
    if fh_sym:
        fq = _finnhub_quote(fh_sym)
        if fq:
            price, prev = fq["price"], fq["prev"] or prev
            src = "Finnhub"
    if price is None:
        return f"「{q}」暂时取不到行情。", "nodata"
    label = (tq and tq["name"]) or name or q
    code_show = fh_sym or (qt_code[2:].upper() if qt_code.startswith("us") else qt_code[2:])
    cur = (tq["cur"] if tq else "") or ("USD" if qt_code.startswith("us") else "")
    lines = [f"{label}（{code_show}）", f"现价：{_fmt(price)} {cur}".rstrip()]
    try:
        m15 = _minute_15(minute_code)
    except Exception:
        m15 = None
    if m15:
        last, old, hhmm, bdate = m15
        hm = f"{hhmm[:2]}:{hhmm[2:]}"
        if qt_code.startswith("us"):
            note = f"（截至美东 {hm}）"
        else:
            stale = bdate != time.strftime("%Y%m%d") or hhmm < time.strftime("%H%M", time.localtime(time.time() - 300))
            note = f"（非交易时段，为 {hm} 前最后15分钟）" if stale else ""
        base = last if note else price
        lines.append(f"15分钟：{_chg(base, old)}{note}")
    else:
        lines.append("15分钟：暂无分时数据（未开盘或盘前）")
    if prev:
        lines.append(f"今日：{_chg(price, prev)}")
    if tq and tq.get("time"):
        t = re.sub(r"[/]", "-", tq["time"])
        if re.fullmatch(r"\d{14}", t):
            t = f"{t[:4]}-{t[4:6]}-{t[6:8]} {t[8:10]}:{t[10:12]}:{t[12:]}"
        lines.append(f"数据：{src} {t}")
    elif src == "Finnhub":
        lines.append("数据：Finnhub")
    return "\n".join(lines), src


def handle(chat, text):
    """是行情命令就返回回复文字（冷却中返回 ''），否则返回 None。从不抛异常。"""
    q = parse(text)
    if q is None:
        return None
    key = (chat, q.lower())
    if time.time() - _cool.get(key, 0) < COOLDOWN_SEC:
        print(f"[stock] cooldown {chat} /{q}")
        return ""
    _cool[key] = time.time()
    try:
        sym = CRYPTO.get(q.lower()) or CRYPTO.get(q)
        reply, src = crypto(sym) if sym else stock(q)
        if reply is None:
            print(f"[stock] notfound /{q}")
            return f"没找到「{q}」对应的股票或币种。" if re.search(r"[\u4e00-\u9fff\d]", q) else None
        print(f"[stock] ok /{q} src={src}")
        return reply
    except Exception as e:
        print(f"[stock] fail /{q}: {type(e).__name__}: {str(e)[:120]}")
        return f"「{q}」行情暂时获取失败，稍后再试。"


if __name__ == "__main__":
    import sys
    for a in sys.argv[1:] or ["/btc", "/英伟达", "/苹果", "/AAPL", "/600519", "/nvidia", "/hello"]:
        print("==", a, "->", repr(handle("test", a)))
