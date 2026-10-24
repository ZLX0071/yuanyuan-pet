"""养成数值与时间演化（T2.1/T2.2/T2.4）

数值：hunger 饱食度 / mood 心情（0~100，随时间衰减）；intimacy 亲密度（只涨不跌）。
交互效果与成长阈值来自宠物包 life 段（数据驱动）；离线按经过时间补偿（上限 24h）。
"""

from __future__ import annotations

import time

from ..content.models import PetPack

DEFAULT_DECAY = {"hunger": 4.0, "mood": 3.0}  # 每小时
DEFAULT_INTERACTIONS = {
    "feed": {"hunger": 35, "mood": 12, "intimacy": 1, "state": "eat", "duration_s": 4},
    "pet": {"mood": 6, "intimacy": 1, "state": "excited", "duration_s": 2},
}
DEFAULT_GROWTH = [{"stage": "幼年期", "min_intimacy": 0}]
MAX_OFFLINE_H = 24.0


class Evolution:
    def __init__(self, pack: PetPack, save):
        self.pack = pack
        self.save = save
        st = save.get("stats") or {}
        self.hunger = float(st.get("hunger", 80.0))
        self.mood = float(st.get("mood", 80.0))
        self.intimacy = float(st.get("intimacy", 0.0))

        self.stage = self._stage_for(self.intimacy)  # 先定阶段，离线播报要用

        last = float(save.get("last_seen", time.time()))
        offline_h = min(max((time.time() - last) / 3600.0, 0.0), MAX_OFFLINE_H)
        if offline_h > 0.02:
            self._decay(offline_h)
            print(f"[养成] 离开 {offline_h:.1f} 小时后回来：{self.summary()}", flush=True)

        self.save_stats()

    # ---- 演化 ----
    def _decay(self, hours: float) -> None:
        rates = self.pack.life_decay or DEFAULT_DECAY
        self.hunger = max(0.0, self.hunger - float(rates.get("hunger", 4.0)) * hours)
        mood_rate = float(rates.get("mood", 3.0)) + (2.0 if self.hunger < 25 else 0.0)
        self.mood = max(0.0, min(100.0, self.mood - mood_rate * hours))

    def tick(self, hours: float) -> None:
        self._decay(hours)

    # ---- 交互（喂食/摸摸头，效果来自宠物包 life.interactions）----
    def do(self, interaction_id: str) -> tuple[str, float] | None:
        cfg = (self.pack.life_interactions or {}).get(interaction_id) \
            or DEFAULT_INTERACTIONS.get(interaction_id)
        if not cfg:
            return None
        self.hunger = min(100.0, self.hunger + float(cfg.get("hunger", 0)))
        self.mood = min(100.0, self.mood + float(cfg.get("mood", 0)))
        self.intimacy = min(100.0, self.intimacy + float(cfg.get("intimacy", 0)))
        self.save_stats()
        state = cfg.get("state")
        duration = float(cfg.get("duration_s", 0)) or None
        return (state, duration) if state else None

    # ---- 成长阶段（T2.4）----
    def _stage_for(self, intimacy: float) -> str:
        stages = self.pack.growth_stages or DEFAULT_GROWTH
        current = stages[0]
        for s in stages:
            if intimacy >= float(s.get("min_intimacy", 0)):
                current = s
        return current.get("stage", "幼年期")

    def check_growth(self) -> str | None:
        """阶段变化时返回新阶段名，否则 None"""
        new = self._stage_for(self.intimacy)
        if new != self.stage:
            self.stage = new
            self.save_stats()
            return new
        return None

    # ---- 状态机接口 / 持久化 ----
    def as_dict(self) -> dict:
        return {"hunger": self.hunger, "mood": self.mood, "intimacy": self.intimacy}

    def save_stats(self) -> None:
        self.save.set("stats", self.as_dict())
        self.save.set("last_seen", time.time())

    def summary(self) -> str:
        return f"饱食 {self.hunger:.0f} / 心情 {self.mood:.0f} / 亲密度 {self.intimacy:.0f}（{self.stage}）"
