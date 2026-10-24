"""全局键鼠监听 + 前台窗口/全屏轮询（T3.1 选型：pynput，Windows）

约定：pynput 回调运行在监听线程——回调里只入队/写时间戳，绝不触碰 Qt。
鼠标移动事件频率极高，只原子更新时间戳，不进队列。
隐私：全部在内存，无任何落盘。
"""

from __future__ import annotations

import ctypes
import queue
import time


def start_hooks(raw_q: "queue.Queue") -> dict:
    """启动三个后台监听（键盘 / 鼠标 / 全局热键 Ctrl+Alt+Y），返回句柄字典。"""
    from pynput import keyboard, mouse

    state = {"last_move": time.monotonic()}

    def on_press(_key) -> None:
        raw_q.put(("key", time.monotonic()))

    def on_click(_x, _y, _button, pressed) -> None:
        if pressed:
            raw_q.put(("click", time.monotonic()))

    def on_scroll(*_args) -> None:
        raw_q.put(("scroll", time.monotonic()))

    def on_move(_x, _y) -> None:
        state["last_move"] = time.monotonic()  # GIL 下浮点赋值原子，够用

    kb = keyboard.Listener(on_press=on_press)
    kb.start()
    ms = mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
    ms.start()
    hot = keyboard.GlobalHotKeys({"<ctrl>+<alt>+y": lambda: raw_q.put(("hotkey_silent", time.monotonic()))})
    hot.start()
    return {"keyboard": kb, "mouse": ms, "hotkeys": hot, "state": state}


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong),
                ("rcMonitor", _RECT), ("rcWork", _RECT),
                ("dwFlags", ctypes.c_ulong)]


class ForegroundPoller:
    """轮询前台窗口（判全屏 + app_switch）。4Hz 轮询成本可忽略。"""

    def __init__(self):
        self.user32 = ctypes.windll.user32
        self._last_hwnd = None

    def poll(self) -> tuple[int | None, bool]:
        hwnd = self.user32.GetForegroundWindow()
        if self._last_hwnd is None:
            changed = False  # 首次观测不算切换
        else:
            changed = hwnd != self._last_hwnd
        self._last_hwnd = hwnd
        return hwnd, changed

    def is_fullscreen(self, hwnd: int | None) -> bool:
        """前台窗口矩形 == 所在显示器矩形（±2px）视为全屏（看视频/游戏）。"""
        if not hwnd:
            return False
        rect = _RECT()
        if not self.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False
        mi = _MONITORINFO()
        mi.cbSize = ctypes.sizeof(_MONITORINFO)
        monitor = self.user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        if not monitor or not self.user32.GetMonitorInfoW(monitor, ctypes.byref(mi)):
            return False
        m, r = mi.rcMonitor, rect
        return (abs(m.left - r.left) <= 2 and abs(m.top - r.top) <= 2
                and abs(m.right - r.right) <= 2 and abs(m.bottom - r.bottom) <= 2)
