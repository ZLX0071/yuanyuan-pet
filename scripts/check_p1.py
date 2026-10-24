"""P1/P2 验收：长期记忆摘要（假 Provider）/ RRULE 展开 / 记忆注入

运行：python scripts/check_p1.py
"""

import datetime
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from yuanyuan.ai import memory as pet_memory  # noqa: E402
from yuanyuan.life.save import Save  # noqa: E402
from yuanyuan.sense.calendar import _expand_rrule  # noqa: E402

results: list[tuple[bool, str]] = []


def check(ok: bool, msg: str) -> None:
    results.append((ok, msg + (" ✅" if ok else " ❌")))


class FakeProvider:
    def __init__(self, reply):
        self.reply = reply

    def chat(self, messages):
        return self.reply, 10


def main() -> int:
    # 1. 长期记忆：溢出摘要 + FIFO 上限 + 注入块
    with tempfile.TemporaryDirectory() as tmp:
        save = Save(Path(tmp) / "t.db")
        # 不够阈值不摘要
        save.set("chat_history", [{"role": "user", "content": "hi"}] * 5)
        check(pet_memory.maintain(save, FakeProvider('["x"]')) == [], "未到阈值不摘要")
        # 超阈值 → 摘要最旧 10 条，历史收缩
        save.set("chat_history", [{"role": "user", "content": f"m{i}"} for i in range(25)])
        new = pet_memory.maintain(save, FakeProvider('["主人喜欢喝美式", "主人养了一只猫"]'))
        check(new == ["主人喜欢喝美式", "主人养了一只猫"], "摘要出事实")
        check(len(save.get("chat_history")) == 15, "历史收缩为 15 条（25-10）")
        facts = save.get("memory_facts")
        check(facts == ["主人喜欢喝美式", "主人养了一只猫"], "事实落库")
        # 无 Provider 不摘要不报错
        save.set("chat_history", [{"role": "user", "content": "x"}] * 25)
        check(pet_memory.maintain(save, None) == [] and len(save.get("chat_history")) == 25,
              "无 AI 时不摘要（fail-open，历史保留）")
        # 坏回复容错
        save.set("chat_history", [{"role": "user", "content": "x"}] * 25)
        check(pet_memory.maintain(save, FakeProvider("这不是JSON")) == [], "坏回复静默跳过")
        # 注入块
        block = pet_memory.inject_block(save)
        check("主人喜欢喝美式" in block and "长期记得" in block, "注入块包含事实")
        save.close()

    # 2. RRULE 展开
    base = datetime.datetime(2099, 1, 1, 9, 0)  # 周四
    now = datetime.datetime(2099, 1, 1, 0, 0)
    daily = _expand_rrule("FREQ=DAILY", base, now, horizon_days=3)
    check(len(daily) == 3 and daily[0] == base, "DAILY 展开 3 天")
    check(_expand_rrule("FREQ=DAILY;INTERVAL=2", base, now, 3)[:2] ==
          [base, base + datetime.timedelta(days=2)], "INTERVAL=2 隔天")
    weekly = _expand_rrule("FREQ=WEEKLY;BYDAY=MO,FR", base, now, 7)
    days = {d.weekday() for d in weekly}
    check(days == {0, 4} and len(weekly) == 2, f"WEEKLY BYDAY=MO,FR（实际 {sorted(days)}）")
    now2 = datetime.datetime(2099, 1, 3, 0, 0)  # 从 1/3 起算，1/1 已过
    check(_expand_rrule("FREQ=DAILY", base, now2, 2) ==
          [datetime.datetime(2099, 1, 3, 9, 0), datetime.datetime(2099, 1, 4, 9, 0)],
          "过去的 occurrence 不出现")

    failed = [msg for ok, msg in results if not ok]
    print("\n".join(msg for ok, msg in results if ok))
    if failed:
        print("\n".join(failed))
        print(f"\n❌ {len(failed)} 项未通过")
        return 1
    print(f"\n✅ P1/P2 验收全部通过（{len(results)} 项）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
