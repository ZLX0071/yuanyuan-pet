"""T1.4 验收：加载器正例 + 5 个坏包负例，全部要报"人话"。

运行：python scripts/check_loader.py（全部通过时退出码 0）
"""

import base64
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from yuanyuan.content.pack_loader import PackError, load_pack  # noqa: E402

PROJ_ROOT = Path(__file__).resolve().parents[1]

# 1x1 透明 PNG
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

results: list[tuple[bool, str]] = []


def expect_error(case: str, setup, keyword: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        pack = Path(tmp) / "bad-pack"
        setup(pack)
        try:
            load_pack(pack)
            results.append((False, f"{case}：本应拒载却加载成功了"))
        except PackError as e:
            ok = keyword in str(e)
            results.append((ok, f"{case}：『{e}』{'✅' if ok else '❌ 关键词缺失: ' + keyword}"))


def s_manifest_missing(p: Path) -> None:
    p.mkdir(parents=True)


def s_bad_json(p: Path) -> None:
    p.mkdir(parents=True)
    (p / "manifest.json").write_text("{ 这是坏 json", encoding="utf-8")


def s_no_name(p: Path) -> None:
    p.mkdir(parents=True)
    (p / "manifest.json").write_text(json.dumps({"states": {}}), encoding="utf-8")


def s_no_states(p: Path) -> None:
    p.mkdir(parents=True)
    (p / "manifest.json").write_text(
        json.dumps({"meta": {"name": "X", "license": "CC0"}}), encoding="utf-8")


def s_missing_frames(p: Path) -> None:
    p.mkdir(parents=True)
    (p / "manifest.json").write_text(json.dumps({
        "meta": {"name": "X", "license": "CC0"},
        "states": {"idle": {"frames": "sprites/idle/idle_*.png"}},
    }), encoding="utf-8")


def s_dangling_ref(p: Path) -> None:
    (p / "sprites" / "idle").mkdir(parents=True)
    (p / "sprites" / "idle" / "idle_0.png").write_bytes(TINY_PNG)
    (p / "manifest.json").write_text(json.dumps({
        "meta": {"name": "X", "license": "CC0"},
        "states": {"idle": {"frames": "sprites/idle/idle_*.png"}},
        "behaviors": [{"id": "b1", "from": "idle", "to": "ghost",
                       "trigger": {"type": "click"}}],
    }), encoding="utf-8")


def main() -> int:
    # 正例：真实示例包
    try:
        pack = load_pack(PROJ_ROOT / "pets" / "demo-blob")
        results.append((True, f"正例 demo-blob：加载成功 ✅\n{pack.summary()}"))
    except PackError as e:
        results.append((False, f"正例 demo-blob 意外失败：{e}"))

    expect_error("缺 manifest", s_manifest_missing, "缺少 manifest.json")
    expect_error("坏 JSON", s_bad_json, "不是合法 JSON")
    expect_error("缺 meta.name", s_no_name, "meta.name")
    expect_error("缺 states", s_no_states, "没有 states")
    expect_error("帧缺失", s_missing_frames, "找不到任何帧图片")
    expect_error("行为引用幽灵状态", s_dangling_ref, "未定义的状态")

    # 警告路径：缺 license 应警告不拒载
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "no-license"
        (p / "sprites" / "idle").mkdir(parents=True)
        (p / "sprites" / "idle" / "idle_0.png").write_bytes(TINY_PNG)
        (p / "manifest.json").write_text(json.dumps({
            "meta": {"name": "X"},
            "states": {"idle": {"frames": "sprites/idle/idle_*.png"}},
        }), encoding="utf-8")
        pack = load_pack(p)
        ok = any("license" in w for w in pack.warnings)
        results.append((ok, f"缺 license：仅警告不拒载 {'✅' if ok else '❌'}（warnings={pack.warnings}）"))

    failed = [msg for ok, msg in results if not ok]
    print("\n".join(msg for ok, msg in results if ok))
    if failed:
        print("\n".join(failed))
        print(f"\n❌ {len(failed)} 项未通过")
        return 1
    print(f"\n✅ 加载器验收全部通过（{len(results)} 项）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
