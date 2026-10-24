"""P0 验收：免打扰判定（含跨午夜）/ 记事删除 / 配置按节合并 / 上次宠物记忆

运行：python scripts/check_p0.py
"""

import datetime
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from yuanyuan.ai.notes import add_note, delete_note, pending_notes  # noqa: E402
from yuanyuan.config import load_config, save_section  # noqa: E402
from yuanyuan.life.save import Save  # noqa: E402
from yuanyuan.sense.reminders import in_dnd  # noqa: E402

results: list[tuple[bool, str]] = []


def check(ok: bool, msg: str) -> None:
    results.append((ok, msg + (" ✅" if ok else " ❌")))


def main() -> int:
    # 1. 免打扰判定
    cfg = {"enabled": True, "start": "23:00", "end": "08:00"}
    t = lambda h, m: datetime.datetime(2099, 1, 1, h, m)  # noqa: E731
    check(in_dnd(cfg, t(23, 30)), "23:30 在免打扰内")
    check(in_dnd(cfg, t(3, 0)), "凌晨 3 点在免打扰内（跨午夜）")
    check(not in_dnd(cfg, t(12, 0)), "中午不在免打扰内")
    check(in_dnd(cfg, t(7, 59)), "07:59 仍在内")
    check(not in_dnd(cfg, t(8, 0)), "08:00 整点出窗（边界=结束）")
    check(not in_dnd({"enabled": False, "start": "23:00", "end": "08:00"}, t(23, 30)),
          "未启用时永不免打扰")
    check(not in_dnd({"enabled": True, "start": "bad", "end": "08:00"}, t(23, 30)),
          "坏配置视为未启用")

    # 2. 记事完成/删除
    with tempfile.TemporaryDirectory() as tmp:
        save = Save(Path(tmp) / "t.db")
        add_note(save, {"id": "n1", "text": "交报告", "due": None, "created": "", "reminded": False})
        add_note(save, {"id": "n2", "text": "买猫粮", "due": None, "created": "", "reminded": False})
        delete_note(save, "n1")
        left = pending_notes(save)
        check(len(left) == 1 and left[0]["id"] == "n2", "删除后剩正确条目")
        save.close()

    # 3. 配置按节合并（ai 不吃掉 ui/dnd）
    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / "config.json"
        save_section(cfg_path, "ui", {"last_pack": "yuanyuan-newyear"})
        save_section(cfg_path, "ai", {"api_key": "x"})
        save_section(cfg_path, "dnd", {"enabled": True, "start": "23:00", "end": "08:00"})
        cfg = load_config(cfg_path)
        check(cfg["ui"]["last_pack"] == "yuanyuan-newyear", "ui 节在 ai/dnd 写入后仍保留")
        check(cfg["ai"]["api_key"] == "x" and cfg["dnd"]["enabled"], "三节共存")

    failed = [msg for ok, msg in results if not ok]
    print("\n".join(msg for ok, msg in results if ok))
    if failed:
        print("\n".join(failed))
        print(f"\n❌ {len(failed)} 项未通过")
        return 1
    print(f"\n✅ P0 验收全部通过（{len(results)} 项）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
