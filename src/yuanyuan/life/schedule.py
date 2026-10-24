"""X1 作息还原：用户"教"缘缘自己的作息，缘缘按节奏自主生活（零 AI 成本）。

数据存在 Save（用户数据，不属于宠物包）：schedule = {"enabled": bool, "entries":
[{"time": "HH:MM", "state": 状态名, "label": 说明, "duration_s": 秒或 null(持续到互动)}]}。
每条目每天最多触发一次；跨天自动重置。
"""

from __future__ import annotations

import datetime

DEFAULT_SCHEDULE = {
    "enabled": False,
    "entries": [
        {"time": "07:30", "state": "idle", "label": "起床", "duration_s": 4},
        {"time": "12:00", "state": "eat", "label": "午饭", "duration_s": 6},
        {"time": "23:00", "state": "sleep", "label": "睡觉", "duration_s": None},
    ],
}


class ScheduleEngine:
    def __init__(self, save, pack_states: set[str]):
        self.save = save
        self.pack_states = pack_states
        self.reload()

    def reload(self) -> None:
        cfg = self.save.get("schedule") or {}
        merged = {**DEFAULT_SCHEDULE, **cfg}
        self.enabled = bool(merged.get("enabled", False))
        # 过滤引用了未定义状态的条目（宠物包换了不至于崩）
        self.entries = [dict(e) for e in merged.get("entries", [])
                        if e.get("time") and e.get("state") in self.pack_states]
        fired = self.save.get("schedule_fired") or {}
        # 以已存档的天数为基准；首次 tick 时若与真实日期不符会自动重置
        self._day = fired.get("day") or datetime.date.today().isoformat()
        self._fired: set[str] = set(fired.get("keys", [])) if fired.get("day") == self._day else set()

    def _mark(self, key: str) -> None:
        self._fired.add(key)
        self.save.set("schedule_fired", {"day": self._day, "keys": sorted(self._fired)})

    def tick(self, now: datetime.datetime) -> list[dict]:
        """由高频定时器调用；返回当前这一分钟应当触发的条目（每条每天一次）。"""
        if not self.enabled:
            return []
        day = now.date().isoformat()
        if day != self._day:
            self._day = day
            self._fired = set()
        minute = now.strftime("%H:%M")
        out = []
        for e in self.entries:
            key = f"{e['time']}|{e['state']}|{e.get('label', '')}"
            if e["time"] == minute and key not in self._fired:
                self._mark(key)
                out.append(e)
        return out
