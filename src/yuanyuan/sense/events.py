"""感知事件聚合器（T3.2）—— 原始键鼠事件 → 高层事件，纯逻辑、可注入时间、只在内存

高层事件：typing_burst（持续打字）/ work_marathon（久坐工作）/ long_idle（人离开）
        / user_return（人回来了）/ app_switch（切换前台窗口）
隐私约定：一切只在内存，绝不落盘、绝不上传（PRD 交互铁律 4）。
"""

from __future__ import annotations

import collections


class SenseAggregator:
    """阈值全部用秒（应用层负责分钟→秒换算），now 由调用方注入以便测试。"""

    def __init__(self, t0: float = 0.0,
                 idle_s: float = 600.0,
                 typing_s: float = 300.0, typing_gap_s: float = 3.0,
                 burst_cd_s: float = 900.0,
                 work_s: float = 3600.0, break_gap_s: float = 300.0,
                 marathon_cd_s: float = 3600.0,
                 switch_stable_s: float = 5.0, switch_cd_s: float = 60.0):
        self.idle_s = idle_s
        self.typing_s = typing_s
        self.typing_gap_s = typing_gap_s
        self.burst_cd_s = burst_cd_s
        self.work_s = work_s
        self.break_gap_s = break_gap_s
        self.marathon_cd_s = marathon_cd_s
        self.switch_stable_s = switch_stable_s
        self.switch_cd_s = switch_cd_s

        self.t0 = t0
        self.last_input = t0        # 最近一次真实输入（键/点击/滚动/移动）
        self.last_key = None        # 最近一次按键
        self.typing_start = None    # 当前打字连击段起点
        self.episode_start = t0     # 当前活跃段落起点（间隔超过 break_gap 视为新段落）
        self._away = False          # long_idle 已触发（每段离开只报一次）
        self._return_pending = False
        self._switch_candidate = None
        self._fired = collections.defaultdict(lambda: -1e18)
        self.out: collections.deque = collections.deque()
        self.last_move_seen = 0.0   # 鼠标移动走时间戳旁路（见 hooks），由应用层对比后喂入

    # ---- 喂入（钩子线程只做这两类调用，全部 O(1)）----
    def feed(self, kind: str, t: float) -> None:
        if kind == "switch":
            self._switch_candidate = t
            return
        if self._away:
            self._away = False
            self._return_pending = True  # 离开后首次输入 → 人回来了
        if t - self.last_input > self.break_gap_s:
            self.episode_start = t       # 中断够久：久坐段落重新起算
        self.last_input = t
        if kind == "key":
            if self.last_key is None or t - self.last_key > self.typing_gap_s:
                self.typing_start = t
            self.last_key = t

    def set_foreground_changed(self, t: float) -> None:
        """前台窗口变化（应用层轮询发现），带防抖地转为 app_switch"""
        self._switch_candidate = t

    # ---- 计算（应用层定时调用）----
    def poll(self, now: float) -> list[str]:
        if self._return_pending:
            self._return_pending = False
            self.out.append("user_return")

        if not self._away and now - self.last_input >= self.idle_s:
            self._away = True
            self.out.append("long_idle")

        if (self.last_key is not None and self.typing_start is not None
                and now - self.last_key <= self.typing_gap_s
                and now - self.typing_start >= self.typing_s
                and now - self._fired["typing_burst"] >= self.burst_cd_s):
            self._fired["typing_burst"] = now
            self.out.append("typing_burst")

        if (now - self.episode_start >= self.work_s
                and now - self._fired["work_marathon"] >= self.marathon_cd_s):
            self._fired["work_marathon"] = now
            self.episode_start = now  # 段落重置，下一个周期再报
            self.out.append("work_marathon")

        if (self._switch_candidate is not None
                and now - self._switch_candidate >= self.switch_stable_s
                and now - self._fired["app_switch"] >= self.switch_cd_s):
            self._fired["app_switch"] = now
            self._switch_candidate = None
            self.out.append("app_switch")

        out = list(self.out)
        self.out.clear()
        return out
