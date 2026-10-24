"""动画状态机（T1.5）—— 切换规则完全来自宠物包，引擎不内置任何具体宠物"""

from __future__ import annotations

import random
import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap

from ..content.models import Behavior, PetPack

EVENT_TRIGGERS = {"click", "double_click", "drag_start", "drag_end"}


class StateMachine(QObject):
    state_changed = pyqtSignal(str, str)  # old, new

    def __init__(self, pack: PetPack, pixmaps: dict[str, list[QPixmap]], stats_getter=None):
        super().__init__()
        self.pack = pack
        self.pixmaps = pixmaps
        self.stats_getter = stats_getter  # 返回养成数值 dict；None = 养成层未接入
        self.current = pack.startup_state or pack.default_state
        self._frame_t0 = time.monotonic()
        self._last_interaction = time.monotonic()
        self._behavior_until: float | None = (
            time.monotonic() + pack.startup_duration if pack.startup_state else None
        )
        self._locked = False  # 拖拽中：只允许 drag_end
        self._decision_timer = QTimer(self)
        self._decision_timer.timeout.connect(self._tick)
        self._decision_timer.start(100)  # 10Hz 决策

    # ---- 播放 ----
    def current_pixmap(self) -> QPixmap:
        frames = self.pixmaps[self.current]
        state = self.pack.states[self.current]
        if len(frames) == 1 or state.fps <= 0:
            return frames[0]
        elapsed = time.monotonic() - self._frame_t0
        idx = int(elapsed * state.fps)
        if state.loop:
            idx %= len(frames)
        else:
            idx = min(idx, len(frames) - 1)
        return frames[idx]

    # ---- 引擎事件入口（窗口层调用）----
    def on_event(self, event: str) -> None:
        self._last_interaction = time.monotonic()
        if event == "drag_end":
            self._locked = False
        for b in self.pack.behaviors:
            if b.trigger.type == event and self._can_fire(b):
                self.fire(b)
                return

    # ---- 决策 ----
    def _tick(self) -> None:
        now = time.monotonic()
        if self._behavior_until is not None and now >= self._behavior_until:
            self._behavior_until = None
            self._transition(self.pack.default_state)
            return
        for b in self.pack.behaviors:
            t = b.trigger.type
            if t == "random":
                every = b.trigger.params.get("every_s") or [60, 180]
                nxt = getattr(b, "_next_fire", None)
                if nxt is None:
                    b._next_fire = now + random.uniform(*map(float, every))  # noqa: B010
                    continue
                if now >= nxt:
                    b._next_fire = now + random.uniform(*map(float, every))
                    if self._can_fire(b):
                        self.fire(b)
                        return
            elif t == "idle_time":
                if now - self._last_interaction >= float(b.trigger.params.get("s", 300)):
                    if self._can_fire(b):
                        self.fire(b)
                        return
            elif t == "stat":
                # 条件满足且可触发时立即触发；不满足（如被拖拽锁定）下个周期重试
                if self._stat_met(b.trigger.params) and self._can_fire(b):
                    self.fire(b)
                    return
            # sense：M3 前惰性（见规范 v0 实现约定）

    def _can_fire(self, b: Behavior) -> bool:
        if self._locked:
            return False
        if b.to_state == self.current:
            return False
        if not self._stat_met(b.require):
            return False
        return "*" in b.from_states or self.current in b.from_states

    def _stat_met(self, req: dict | None) -> bool:
        """数值条件判断（stat 触发器与 require 门槛共用）"""
        if not req:
            return True
        if self.stats_getter is None:
            return False
        vals = self.stats_getter()
        v = float(vals.get(req.get("stat"), 0.0))
        t = float(req.get("value", 0.0))
        op = req.get("op", "<")
        return {"<": v < t, "<=": v <= t, ">": v > t, ">=": v >= t, "==": v == t}[op]

    def force(self, state: str, duration: float | None = None) -> bool:
        """交互/系统强制切换（喂食动画、进化庆祝等）"""
        if state not in self.pack.states:
            return False
        self._transition(state)
        self._behavior_until = time.monotonic() + duration if duration else None
        return True

    def fire(self, b: Behavior) -> None:
        self._transition(b.to_state)
        if b.duration:
            self._behavior_until = time.monotonic() + random.uniform(*b.duration)

    def _transition(self, new: str) -> None:
        if new == self.current:
            return
        old, self.current = self.current, new
        self._frame_t0 = time.monotonic()
        self._behavior_until = None
        if new == "drag":  # 进入拖拽态后锁住，直到 drag_end
            self._locked = True
        self.state_changed.emit(old, new)
