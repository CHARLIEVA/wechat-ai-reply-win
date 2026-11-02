# -*- coding: utf-8 -*-
"""Keep the WeChat window small and in the background.  让微信窗口保持小窗、放在最底层、不抢前台。

wxauto4 calls ShowWindow + SwitchToThisWindow before every UI read, which pops WeChat to the
front. We patch that so reads only un-minimize without activating; real activation happens only
while a message is being sent (see `sending()`).
wxauto4 每次读界面都会把微信拉到最前面。这里改成：读取时只取消最小化、不激活；
只有真正发送消息时（`sending()` 上下文内）才允许激活。

Note: wxauto4 cannot attach to a *minimized* WeChat window, so we use a small window at the
bottom of the Z-order instead of minimizing.  注意：微信最小化后 wxauto4 无法连接，所以改为小窗+最底层。
Size: WX_WIN_W / WX_WIN_H (default 1000x760).  Disable: WX_WINDOW_QUIET=false.
"""
import contextlib
import os

ENABLED = (os.environ.get("WX_WINDOW_QUIET", "true").strip().lower() in ("1", "true", "yes", "on"))
WIN_W = int(os.environ.get("WX_WIN_W", "1000") or 1000)
WIN_H = int(os.environ.get("WX_WIN_H", "760") or 760)
WINDOW_TITLE = os.environ.get("WX_WINDOW_TITLE", "微信")

_SENDING = {"on": False}
_patched = False

try:
    import win32gui  # pywin32 (installed with wxauto4)
except Exception:  # pragma: no cover - non-Windows
    win32gui = None


def install():
    """Patch wxauto4 so UI reads don't steal focus. Call before WeChat()."""
    global _patched
    if not ENABLED or _patched or win32gui is None:
        return False
    try:
        from wxauto4.ui import base as _wxbase
    except Exception:
        return False
    orig = _wxbase.BaseUIWnd._show

    def _quiet_show(self):
        if _SENDING["on"]:
            return orig(self)  # sending: allow normal activation / 发送时正常激活
        try:
            h = getattr(self, "HWND", None) or self.control.NativeWindowHandle
            if h and win32gui.IsIconic(h):
                win32gui.ShowWindow(h, 4)  # SW_SHOWNOACTIVATE
        except Exception:
            pass

    _wxbase.BaseUIWnd._show = _quiet_show
    _patched = True
    return True


@contextlib.contextmanager
def sending():
    """Wrap wx.SendMsg calls with this. 发送消息时用它包住。"""
    _SENDING["on"] = True
    try:
        yield
    finally:
        _SENDING["on"] = False


def to_back(resize=False):
    """Move WeChat to the bottom of the Z-order without activating it (optionally resize)."""
    if not ENABLED or win32gui is None:
        return
    try:
        h = win32gui.FindWindow(None, WINDOW_TITLE)
        if not h:
            return
        if win32gui.IsIconic(h):
            win32gui.ShowWindow(h, 4)
        flags = 0x10 | 0x2 | (0 if resize else 0x1)  # NOACTIVATE | NOMOVE | (NOSIZE)
        win32gui.SetWindowPos(h, 1, 0, 0, WIN_W, WIN_H, flags)  # HWND_BOTTOM
    except Exception:
        pass
