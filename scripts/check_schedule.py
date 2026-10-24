"""X1 验收：作息引擎（触发时机/每天一次/跨天重置/无效状态过滤/重启不重触发）

运行：python scripts/check_schedule.py
"""

import datetime
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from yuanyuan.life.save import Save  # noqa: E402
from yuanyuan.life.schedule import ScheduleEngine  # noqa: E402

results: list[tuple[bool, str]] = []


def check(ok: bool, msg: str) -> None:
    results.append((ok, msg + (" ✅" if ok else " ❌")))


STATES = {"idle", "eat", "sleep"}


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        save = Save(Path(tmp) / "t.db")
        save.set("schedule", {
            "enabled": True,
            "entries": [
                {"time": "07:30", "state": "idle", "label": "起床", "duration_s": 4},
                {"time": "12:00", "state": "eat", "label": "午饭", "duration_s": 6},
                {"time": "13:00", "state": "ghost", "label": "坏数据"},  # 未定义状态应被过滤
            ],
        })

        eng = ScheduleEngine(save, STATES)
        check(len(eng.entries) == 2, "无效状态条目被过滤（剩 2 条）")

        d = datetime.date(2099, 1, 1)
        # 未到点不触发
        check(eng.tick(datetime.datetime.combine(d, datetime.time(7, 29))) == [], "未到点不触发")
        # 到点触发一次
        fired = eng.tick(datetime.datetime.combine(d, datetime.time(7, 30)))
        check(len(fired) == 1 and fired[0]["label"] == "起床", "07:30 触发起床")
        # 同一分钟内不重复
        check(eng.tick(datetime.datetime.combine(d, datetime.time(7, 30, 30))) == [], "同一分钟不重复触发")
        # 其他时间不触发
        check(eng.tick(datetime.datetime.combine(d, datetime.time(8, 30))) == [], "其他时间不触发")
        # 跨天重置后可再触发
        d2 = datetime.date(2099, 1, 2)
        fired2 = eng.tick(datetime.datetime.combine(d2, datetime.time(7, 30)))
        check(len(fired2) == 1, "跨天后重新可触发")

        # 重启（重新 reload）当天不重复触发
        eng2 = ScheduleEngine(save, STATES)
        check(eng2.tick(datetime.datetime.combine(d2, datetime.time(7, 30, 59))) == [],
              "重启后当天已触发条目不重复")

        # 关闭开关 → 不触发
        save.set("schedule", {"enabled": False, "entries": [
            {"time": "07:30", "state": "idle", "label": "起床", "duration_s": 4}]})
        eng3 = ScheduleEngine(save, STATES)
        d3 = datetime.date(2099, 1, 3)
        check(eng3.tick(datetime.datetime.combine(d3, datetime.time(7, 30))) == [], "关闭开关不触发")

        # 12:00 午饭在同一分钟与 07:30 不互斥
        save.set("schedule", {"enabled": True, "entries": [
            {"time": "12:00", "state": "eat", "label": "午饭", "duration_s": 6}]})
        eng4 = ScheduleEngine(save, STATES)
        fired4 = eng4.tick(datetime.datetime.combine(datetime.date(2099, 1, 4), datetime.time(12, 0)))
        check(len(fired4) == 1 and fired4[0]["state"] == "eat", "午饭正常触发")
        save.close()

    failed = [msg for ok, msg in results if not ok]
    print("\n".join(msg for ok, msg in results if ok))
    if failed:
        print("\n".join(failed))
        print(f"\n❌ {len(failed)} 项未通过")
        return 1
    print(f"\n✅ 作息引擎验收全部通过（{len(results)} 项）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
