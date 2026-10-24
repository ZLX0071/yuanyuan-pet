"""M4.5 验收：ICS 解析 / 日历提醒窗口 / 番茄钟 / 记事存储（纯逻辑，不打 AI）

运行：python scripts/check_m45.py
"""

import datetime
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from yuanyuan.ai.notes import add_note, due_notes, mark_reminded, pending_notes  # noqa: E402
from yuanyuan.life.save import Save  # noqa: E402
from yuanyuan.sense.calendar import CalendarWatch, parse_ics  # noqa: E402
from yuanyuan.sense.focus import FocusTimer  # noqa: E402

results: list[tuple[bool, str]] = []


def check(ok: bool, msg: str) -> None:
    results.append((ok, msg + (" ✅" if ok else " ❌")))


ICS_SAMPLE = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:evt-1@x
SUMMARY:项目周会
DTSTART:20990101T090000
DTEND:20990101T100000
END:VEVENT
BEGIN:VEVENT
UID:evt-2@x
SUMMARY:全天生日
DTSTART;VALUE=DATE:20990201
END:VEVENT
BEGIN:VEVENT
UID:evt-3@x
SUMMARY:UTC 会议
DTSTART:20990102T010000Z
END:VEVENT
"""


def main() -> int:
    # 1. ICS 解析：折叠行/浮动时间/全天跳过/UTC 转本地
    events = parse_ics(ICS_SAMPLE)
    check(len(events) == 3, f"解析出 3 个 VEVENT（实际 {len(events)}）")
    check(events[0]["summary"] == "项目周会", "SUMMARY 正确")

    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "cal.ics").write_text(ICS_SAMPLE, encoding="utf-8")
        watch = CalendarWatch(Path(tmp), lead_min=15)
        now = datetime.datetime(2099, 1, 1, 8, 50)  # 距周会 10 分钟
        due = watch.scan(now)
        check(len(due) == 1 and due[0][0] == "项目周会", "提前 15 分钟窗口内提醒周会")
        check(watch.scan(now) == [], "同一事件不重复提醒")
        far = watch.scan(datetime.datetime(2099, 1, 1, 7, 0))
        check(far == [], "窗口外不提醒")
        check(all(e["dtstart"] for e in events), "全天事件保留但不参与提醒")

    # 2. 番茄钟：start → 到点触发一次 → cancel 不触发
    f = FocusTimer(duration_s=25)
    f.start(0.0)
    check(not f.poll(10.0) and f.on, "进行中不触发")
    check(f.poll(25.0) and not f.on, "到点触发一次并自动结束")
    check(not f.poll(30.0), "结束后不再触发")
    f.start(0.0)
    f.cancel()
    check(not f.poll(100.0) and not f.on, "取消后不触发")

    # 3. 记事存储：添加 → 到期筛选 → 标记已提醒
    with tempfile.TemporaryDirectory() as tmp:
        save = Save(Path(tmp) / "t.db")
        add_note(save, {"id": "a1", "text": "周三交 PRD", "due": "2099-01-01 09:00",
                        "created": "", "reminded": False})
        add_note(save, {"id": "a2", "text": "买猫粮", "due": None,
                        "created": "", "reminded": False})
        check(len(pending_notes(save)) == 2, "两条待办")
        check(len(due_notes(save, datetime.datetime(2099, 1, 1, 8, 0))) == 0, "未到时间不触发")
        due = due_notes(save, datetime.datetime(2099, 1, 1, 9, 0))
        check(len(due) == 1 and due[0]["id"] == "a1", "到期触发带时间的记事")
        mark_reminded(save, "a1")
        check(len(due_notes(save, datetime.datetime(2099, 1, 1, 9, 0))) == 0, "标记后不再触发")
        check(len(pending_notes(save)) == 1, "无时间记事保留在待办里")
        save.close()

    failed = [msg for ok, msg in results if not ok]
    print("\n".join(msg for ok, msg in results if ok))
    if failed:
        print("\n".join(failed))
        print(f"\n❌ {len(failed)} 项未通过")
        return 1
    print(f"\n✅ M4.5 逻辑验收全部通过（{len(results)} 项）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
