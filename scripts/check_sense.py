"""T3.2 验收：感知事件聚合器（合成事件时间线 + 单事件成本测量）

运行：python scripts/check_sense.py（全部通过时退出码 0）
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from yuanyuan.sense.events import SenseAggregator  # noqa: E402

results: list[tuple[bool, str]] = []


def check(ok: bool, msg: str) -> None:
    results.append((ok, msg + (" ✅" if ok else " ❌")))


def main() -> int:
    # 阈值全部调小便于测试：打字连击 6s / 久坐 20s / 离开 5s / 冷却 8s/15s
    def make(t0=0.0):
        return SenseAggregator(t0=t0, idle_s=5, typing_s=6, typing_gap_s=1.5,
                               burst_cd_s=8, work_s=20, break_gap_s=10,
                               marathon_cd_s=15, switch_stable_s=2, switch_cd_s=5)

    # 1. 持续打字 → typing_burst 按冷却节奏重复；久坐 20s → work_marathon 且段落重置
    agg = make()
    events = []
    for t in range(0, 36):
        agg.feed("key", float(t))
        events += agg.poll(float(t) + 0.1)
    bursts = [i for i, e in enumerate(events) if e == "typing_burst"]
    check(len(bursts) >= 3, f"持续打字触发多次 typing_burst（{len(bursts)} 次）")
    check("work_marathon" in events, "连续活跃 20s 触发 work_marathon")
    check(events.count("work_marathon") == 1, f"段落重置后 36s 内不再重复（{events.count('work_marathon')} 次）")

    # 2. 离开 → long_idle 一次；回来 → user_return 一次；再离开 → 再 long_idle
    agg = make()
    agg.feed("key", 0.0)
    check(agg.poll(3.0) == [], "未到阈值不触发")
    check(agg.poll(6.0) == ["long_idle"], "闲置 5s 触发 long_idle")
    check(agg.poll(10.0) == [], "离开期间不重复触发")
    agg.feed("key", 12.0)
    check(agg.poll(12.1) == ["user_return"], "回来触发 user_return")
    agg.feed("key", 13.0)
    check(agg.poll(13.1) == [], "回来后短暂活动不误报")
    check(agg.poll(19.0) == ["long_idle"], "再次离开满 5s 再次 long_idle")

    # 3. 久坐段落被长休息打断 → 不触发 marathon
    agg = make()
    for t in range(0, 15):
        agg.feed("key", float(t))
        agg.poll(float(t) + 0.1)
    for t in range(30, 40):  # 休息 15s > break_gap 10s
        agg.feed("key", float(t))
        agg.poll(float(t) + 0.1)
    check("work_marathon" not in [e for e in agg.poll(40.5)],
          "被长休息打断后不触发 work_marathon")

    # 4. 前台切换防抖：稳定 2s 才报，冷却 5s（自上次触发起算）；期间喂输入保持活跃
    agg = make()
    agg.feed("key", 0.5)
    agg.set_foreground_changed(0.0)
    check(agg.poll(1.0) == [], "切换未稳定不报")
    agg.feed("key", 1.2)
    check(agg.poll(2.5) == ["app_switch"], "稳定 2s 后报 app_switch")
    agg.set_foreground_changed(3.0)
    agg.feed("key", 4.0)
    check(agg.poll(4.0) == [], "未稳定且冷却期内（上次触发后 1.5s）不报")
    agg.feed("key", 11.0)
    agg.set_foreground_changed(11.0)
    check(agg.poll(13.0) == ["app_switch"], "稳定且冷却已过（上次触发后 10.5s）再报")

    # 5. 单事件处理成本（选型笔记数据）
    agg = make()
    n = 100_000
    t0 = time.perf_counter()
    for i in range(n):
        agg.feed("key", float(i % 1000))
        agg.poll(1000.0)
    per_event_us = (time.perf_counter() - t0) / n * 1e6
    check(per_event_us < 20, f"单事件处理 {per_event_us:.2f} µs（预算 <20µs）")

    failed = [msg for ok, msg in results if not ok]
    print("\n".join(msg for ok, msg in results if ok))
    if failed:
        print("\n".join(failed))
        print(f"\n❌ {len(failed)} 项未通过")
        return 1
    print(f"\n✅ 感知聚合器验收全部通过（{len(results)} 项）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
