"""提醒调度（T3.4 + P0-3 免打扰）：喝水 / 久坐。全屏/静默/免打扰时段自动延后。"""

from __future__ import annotations

import datetime

DEFAULT_REMINDERS = {
    "water": {"every_min": 45, "message": "汪！陪你去接杯水嘛…", "enabled": True},
    "rest": {"every_min": 60, "message": "盯屏幕很久啦，站起来伸个懒腰！", "enabled": True},
}


def in_dnd(cfg: dict | None, now: datetime.datetime) -> bool:
    """免打扰时段判定；支持跨午夜窗口（如 23:00-08:00）。cfg: {enabled,start,end}"""
    if not cfg or not cfg.get("enabled"):
        return False
    try:
        start = datetime.time.fromisoformat(str(cfg.get("start", "23:00")))
        end = datetime.time.fromisoformat(str(cfg.get("end", "08:00")))
    except ValueError:
        return False
    cur = now.time()
    if start <= end:
        return start <= cur < end
    return cur >= start or cur < end  # 跨午夜


class ReminderScheduler:
    def __init__(self, pack_sense_cfg: dict | None, t0: float = 0.0):
        cfg = (pack_sense_cfg or {}).get("reminders") or {}
        self.items: dict[str, dict] = {}
        for kind, default in DEFAULT_REMINDERS.items():
            item = dict(default)
            item.update(cfg.get(kind) or {})
            item["every_s"] = float(item["every_min"]) * 60
            item["next"] = t0 + item["every_s"]
            self.items[kind] = item

    def set_enabled(self, kind: str, enabled: bool) -> None:
        if kind in self.items:
            self.items[kind]["enabled"] = enabled

    def is_enabled(self, kind: str) -> bool:
        return bool(self.items.get(kind, {}).get("enabled", False))

    def due(self, now: float) -> list[tuple[str, str]]:
        """到期的提醒。调用方若因全屏/静默跳过，不要调 mark_fired → 下个周期继续到期（延后语义）。"""
        return [(kind, it["message"]) for kind, it in self.items.items()
                if it.get("enabled", True) and now >= it["next"]]

    def mark_fired(self, kind: str, now: float) -> None:
        if kind in self.items:
            self.items[kind]["next"] = now + self.items[kind]["every_s"]
