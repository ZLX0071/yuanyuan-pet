"""番茄钟专注陪伴（M4.5-F-D）：缘缘安静陪坐（引擎抑制自动行为），完成有庆祝。"""

from __future__ import annotations


class FocusTimer:
    def __init__(self, duration_s: float = 1500.0):  # 25 分钟
        self.duration = duration_s
        self.end: float | None = None

    @property
    def on(self) -> bool:
        return self.end is not None

    def start(self, now: float) -> float:
        self.end = now + self.duration
        return self.duration

    def cancel(self) -> None:
        self.end = None

    def poll(self, now: float) -> bool:
        """到点返回 True（仅一次）。"""
        if self.end is not None and now >= self.end:
            self.end = None
            return True
        return False

    def remaining_s(self, now: float) -> int:
        return int(self.end - now) if self.end is not None else 0
