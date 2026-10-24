"""养成数值与时间演化（T2.1/T2.2/T2.4）

数值：hunger 饱食度 / mood 心情（0~100，随时间衰减）；intimacy 亲密度（只涨不跌）。
交互效果与成长阈值来自宠物包 life 段（数据驱动）；离线按经过时间补偿（上限 24h）。
"""

from __future__ import annotations

import datetime
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
        self._init_companionship()

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

    # ---- 陪伴仪式感（M2.5-N3）：天数 / 连续陪伴 / 每日首喂双倍 ----
    def _init_companionship(self) -> None:
        today = datetime.date.today().isoformat()
        self.first_day = str(self.save.get("first_day") or today)
        self.save.set("first_day", self.first_day)
        streak = int(self.save.get("streak", 1) or 1)
        last = self.save.get("last_active_date")
        if last != today:
            yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
            self.streak = streak + 1 if last == yesterday else 1  # 断一天重计
            self.save.set("streak", self.streak)
            self.save.set("last_active_date", today)
        else:
            self.streak = streak

    def day_count(self) -> int:
        try:
            first = datetime.date.fromisoformat(self.first_day)
            return (datetime.date.today() - first).days + 1
        except ValueError:
            return 1

    def stage_scale(self) -> float:
        """当前成长阶段对应的体型倍率（N4 成长可视化）"""
        current: dict = {"scale": 1.0}
        for s in (self.pack.growth_stages or []):
            if self.intimacy >= float(s.get("min_intimacy", 0)):
                current = s
        return float(current.get("scale", 1.0))

    # ---- 交互（效果来自宠物包 life.interactions；hunger 可为负=消耗）----
    def do(self, interaction_id: str) -> tuple[str, float] | None:
        """执行交互。返回 (state, duration)；冷却中返回 ("__cooldown__", 0)。"""
        cfg = (self.pack.life_interactions or {}).get(interaction_id) \
            or DEFAULT_INTERACTIONS.get(interaction_id)
        if not cfg:
            return None
        today = datetime.date.today().isoformat()
        gain_mul = 1.0
        if interaction_id == "feed" and self.save.get("last_feed_date") != today:
            gain_mul = 2.0  # 每日首喂双倍亲密度（稀缺感）
            self.save.set("last_feed_date", today)
            print("[养成] 今日首喂，亲密度双倍！", flush=True)
        cd_min = float(cfg.get("cooldown_min", 0) or 0)
        if cd_min > 0:
            last_use = float(self.save.get(f"last_use_{interaction_id}", 0) or 0)
            if time.time() - last_use < cd_min * 60:
                return ("__cooldown__", 0.0)
            self.save.set(f"last_use_{interaction_id}", time.time())
        mood_gain = float(cfg.get("mood", 0))
        if self.mood < 30:
            mood_gain *= 0.5  # 心情低落：蔫了，互动效果减半（数值耦合）
        self.hunger = max(0.0, min(100.0, self.hunger + float(cfg.get("hunger", 0))))
        self.mood = max(0.0, min(100.0, self.mood + mood_gain))
        self.intimacy = min(100.0, self.intimacy + float(cfg.get("intimacy", 0)) * gain_mul)
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
