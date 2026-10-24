"""T2.5 验收：存档持久化 + 损坏自愈（T2.1 附带验证读写）

运行：python scripts/check_save.py（全部通过时退出码 0）
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from yuanyuan.life.save import Save  # noqa: E402

results: list[tuple[bool, str]] = []


def check(ok: bool, msg: str) -> None:
    results.append((ok, msg + (" ✅" if ok else " ❌")))


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.db"

        # 1. 写入 → 关闭 → 重开读取（持久化）
        s1 = Save(db)
        s1.set("stats", {"hunger": 12.5, "mood": 80, "intimacy": 3})
        s1.set("last_seen", 1234567890.0)
        s1.close()
        s2 = Save(db)
        stats = s2.get("stats")
        check(isinstance(stats, dict) and stats.get("hunger") == 12.5,
              f"持久化：重开读到 hunger=12.5（实际 {stats}）")
        check(s2.get("last_seen") == 1234567890.0, "last_seen 读取一致")
        check(s2.get("missing", "默认值") == "默认值", "缺失键返回默认值")

        # 2. 损坏自愈：写垃圾字节 → 应备份 .corrupt-* 并重建
        s2.close()
        db.write_bytes(b"this is not a sqlite database at all" * 64)
        s3 = Save(db)  # 不应抛异常
        check(s3.get("stats") is None, "损坏后自愈：新库为空且可读")
        s3.set("stats", {"hunger": 5})
        s3.close()
        backups = list(Path(tmp).glob("*.corrupt-*"))
        check(len(backups) == 1, f"损坏文件已备份为 .corrupt-*（{[b.name for b in backups]}）")

        # 3. 自愈后的库可正常读写
        s4 = Save(db)
        check(s4.get("stats", {}).get("hunger") == 5, "自愈后的库可正常写入读取")
        s4.close()

    failed = [msg for ok, msg in results if not ok]
    print("\n".join(msg for ok, msg in results if ok))
    if failed:
        print("\n".join(failed))
        print(f"\n❌ {len(failed)} 项未通过")
        return 1
    print(f"\n✅ 存档验收全部通过（{len(results)} 项）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
