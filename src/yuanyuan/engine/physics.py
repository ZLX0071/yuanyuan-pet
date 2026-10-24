"""竖直物理（T1.6）：重力下落 + 弹跳 + 落地静止。水平行走由窗口层驱动。"""

from __future__ import annotations

import time

GRAVITY = 2400.0        # px/s²
RESTITUTION = 0.42      # 弹跳保留速度比例
SETTLE_SPEED = 90.0     # 低于该速度视为停住
MAX_BOUNCES = 2


class VerticalPhysics:
    def __init__(self) -> None:
        self.mode = "rest"          # rest | falling
        self.vy = 0.0
        self._last_t = time.monotonic()
        self._bounces = 0

    def drop(self, vy: float = 0.0) -> None:
        self.mode = "falling"
        self.vy = vy
        self._bounces = 0
        self._last_t = time.monotonic()

    def update(self, bottom_y: float, floor_y: float) -> float:
        """推进物理，返回 bottom_y 的新值。floor_y 为地面（任务栏顶）在窗口坐标系下的 y。"""
        now = time.monotonic()
        dt = min(now - self._last_t, 0.05)
        self._last_t = now
        if self.mode != "falling":
            return bottom_y
        self.vy += GRAVITY * dt
        bottom_y += self.vy * dt
        if bottom_y >= floor_y:
            bottom_y = floor_y
            self._bounces += 1
            if self._bounces > MAX_BOUNCES or abs(self.vy) < SETTLE_SPEED * 2:
                self.mode = "rest"
                self.vy = 0.0
            else:
                self.vy = -self.vy * RESTITUTION
        return bottom_y
