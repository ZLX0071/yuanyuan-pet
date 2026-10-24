"""T6.3 验收：宠物包 zip 导入（正例 + zip slip 拒绝 + 重复拒绝 + 坏包回滚 + 缺 manifest）

运行：python scripts/check_import.py
"""

import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from yuanyuan.content.pack_import import ImportError_, import_pack_zip  # noqa: E402

results: list[tuple[bool, str]] = []


def check(ok: bool, msg: str) -> None:
    results.append((ok, msg + (" ✅" if ok else " ❌")))


def make_zip(zip_path: Path, entries: dict[str, bytes | str]) -> None:
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)


MANIFEST = """{"format_version": "0.1",
  "meta": {"name": "导入测试狗", "license": "CC0"},
  "states": {"idle": {"frames": "sprites/idle/idle_*.png"}},
  "behaviors": []}"""
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6260000000060005"
    "27de3bbb0000000049454e44ae426082")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        pets = tmp / "pets"
        good = tmp / "good.zip"
        make_zip(good, {
            "demo-pet/manifest.json": MANIFEST,
            "demo-pet/sprites/idle/idle_0.png": PNG,
        })

        # 1. 正例导入
        name, warnings = import_pack_zip(good, pets)
        check(name == "导入测试狗", f"导入成功，包名「{name}」")
        check((pets / "demo-pet" / "manifest.json").is_file(), "文件落位正确")

        # 2. 重复导入拒绝
        try:
            import_pack_zip(good, pets)
            check(False, "重复导入应拒绝")
        except ImportError_ as e:
            check("已经有" in str(e), f"重复导入拒绝：{e}")

        # 3. zip slip 拒绝
        evil = tmp / "evil.zip"
        make_zip(evil, {"../evil.txt": "x"})
        try:
            import_pack_zip(evil, pets)
            check(False, "zip slip 应拒绝")
        except ImportError_ as e:
            check("不安全路径" in str(e), f"zip slip 拒绝：{e}")
        check(not (pets / "evil.txt").exists(), "恶意文件未落盘")

        # 4. 缺 manifest 拒绝
        bad1 = tmp / "bad1.zip"
        make_zip(bad1, {"some-folder/readme.txt": "x"})
        try:
            import_pack_zip(bad1, pets)
            check(False, "缺 manifest 应拒绝")
        except ImportError_ as e:
            check("manifest" in str(e), f"缺 manifest 拒绝：{e}")

        # 5. 坏包校验失败回滚（引用幽灵状态）
        bad2 = tmp / "bad2.zip"
        make_zip(bad2, {
            "broken-pet/manifest.json": MANIFEST.replace('"behaviors": []',
                                                         '"behaviors": [{"id":"b","from":"idle","to":"ghost","trigger":{"type":"click"}}]'),
            "broken-pet/sprites/idle/idle_0.png": PNG,
        })
        try:
            import_pack_zip(bad2, pets)
            check(False, "坏包应拒绝")
        except Exception as e:
            check(not (pets / "broken-pet").exists(), f"坏包已回滚（{type(e).__name__}）")

    failed = [msg for ok, msg in results if not ok]
    print("\n".join(msg for ok, msg in results if ok))
    if failed:
        print("\n".join(failed))
        print(f"\n❌ {len(failed)} 项未通过")
        return 1
    print(f"\n✅ 导入验收全部通过（{len(results)} 项）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
