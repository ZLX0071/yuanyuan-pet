"""T1.8：缘缘宠物包制作 —— 参考图 rembg 抠图 → 裁剪缩放 → 组包。

运行：python scripts/cutout_yuanyuan.py
（首次运行会下载 u2net 模型 ~170MB 到 ~/.u2net）
产物：pets/yuanyuan/
"""

import json
import sys
from pathlib import Path

from PIL import Image
from rembg import new_session, remove

# 显式指定 u2net（176MB）——默认的 bria-rmbg-2.0 有 1GB 且对影棚纯背景没必要
SESSION = new_session("u2net")

PROJ_ROOT = Path(__file__).resolve().parents[1]
ASSETS = PROJ_ROOT / "assets" / "缘缘-参考图"
PACK_DIR = PROJ_ROOT / "pets" / "yuanyuan"
TARGET_H = 384
MAX_W = 512

# (参考图, 状态) —— 对应 docs/缘缘宠物包设计.md 的状态映射（M2 起含 P1 姿势）
JOBS = [
    ("01-坐姿吐舌-idle.jpg", "idle"),
    ("06-趴下巴-睡觉.jpg", "dozy"),
    ("07-撅屁股摇尾-兴奋.jpg", "excited"),
    ("09-趴卧闭眼-深睡.jpg", "sleep"),
    ("10-双脚跳起-迎接拎起.jpg", "drag"),
    ("12-叼零食-求投喂.jpg", "hungry"),
    ("02-绿围兜坐姿-进食.jpg", "eat"),
    ("08-叼球-玩耍.jpg", "play"),
]

MANIFEST = {
    "format_version": "0.1",
    "meta": {
        "name": "缘缘",
        "author": "you & ZCode",
        "version": "0.1.0",
        "description": "以家里真实小狗缘缘（奶白色卷毛小型犬）为原型的桌宠",
        "license": "私有素材：用户自有照片及其生成图，仅限本人使用",
    },
    "display": {"scale": 0.42, "anchor": "bottom_center"},  # 0.42 ≈ 161px，用户反馈逐次调小（384→211→161）
    "default_state": "idle",
    "startup_state": "excited",
    "startup_duration_s": 2.5,
    "states": {
        "idle": {"frames": "sprites/idle/idle_*.png", "fps": 1, "loop": True},
        "walk": {"frames": "sprites/idle/idle_*.png", "fps": 1, "loop": True,
                 "movement": {"speed": 30}},  # 照片级立绘：用摇摆+位移模拟颠颠地走
        "dozy": {"frames": "sprites/dozy/dozy_*.png", "fps": 1, "loop": True},
        "sleep": {"frames": "sprites/sleep/sleep_*.png", "fps": 1, "loop": True},
        "excited": {"frames": "sprites/excited/excited_*.png", "fps": 1, "loop": True},
        "drag": {"frames": "sprites/drag/drag_*.png", "fps": 1, "loop": True},
        "hungry": {"frames": "sprites/hungry/hungry_*.png", "fps": 1, "loop": True},
        "eat": {"frames": "sprites/eat/eat_*.png", "fps": 1, "loop": True},
        "play": {"frames": "sprites/play/play_*.png", "fps": 1, "loop": True},
    },
    "behaviors": [
        {"id": "wander", "from": "idle", "to": "walk",
         "trigger": {"type": "random", "every_s": [25, 90]},
         "duration_s": [2, 5], "interruptible": True},
        {"id": "playful", "from": "idle", "to": "play",
         "trigger": {"type": "random", "every_s": [40, 120]},
         "require": {"stat": "mood", "op": ">=", "value": 75},
         "duration_s": [3, 6]},
        {"id": "hungry", "from": ["idle", "walk"], "to": "hungry",
         "trigger": {"type": "stat", "stat": "hunger", "op": "<", "value": 30}},
        {"id": "picked_up", "from": "*", "to": "drag",
         "trigger": {"type": "drag_start"}},
        {"id": "dropped", "from": "drag", "to": "idle",
         "trigger": {"type": "drag_end"}},
        {"id": "get_sleepy", "from": ["idle", "walk", "hungry"], "to": "dozy",
         "trigger": {"type": "idle_time", "s": 120}},  # 睡觉链只从清醒态出发，禁止从 sleep 抢回（防抖动）
        {"id": "fall_asleep", "from": "dozy", "to": "sleep",
         "trigger": {"type": "idle_time", "s": 180}},
        {"id": "wake_from_dozy", "from": "dozy", "to": "idle",
         "trigger": {"type": "click"}},
        {"id": "wake_from_sleep", "from": "sleep", "to": "idle",
         "trigger": {"type": "click"}},
        {"id": "greet", "from": "*", "to": "excited",
         "trigger": {"type": "double_click"}, "duration_s": [2, 3]},
        {"id": "react_typing", "from": "idle", "to": "excited",
         "trigger": {"type": "sense", "event": "typing_burst"}, "duration_s": [3, 5]},
        {"id": "greet_return", "from": ["idle", "walk"], "to": "excited",
         "trigger": {"type": "sense", "event": "user_return"}, "duration_s": [2.5, 3.5]},
        {"id": "nudge_rest", "from": ["idle", "walk", "hungry"], "to": "excited",
         "trigger": {"type": "sense", "event": "work_marathon"}, "duration_s": [3, 4.5]},
    ],
    "sense": {
        "reminders": {
            "water": {"every_min": 45, "message": "汪！陪我去接杯水嘛，就一口…"},
            "rest": {"every_min": 60, "message": "盯屏幕很久啦汪！站起来伸个懒腰，我看着你～"}
        }
    },
    "life": {
        "decay_per_hour": {"hunger": 4.0, "mood": 3.0},
        "interactions": {
            "feed": {"hunger": 35, "mood": 12, "intimacy": 1, "state": "eat", "duration_s": 4},
            "pet": {"mood": 6, "intimacy": 1, "state": "excited", "duration_s": 2}
        },
        "growth": [
            {"stage": "幼年期", "min_intimacy": 0},
            {"stage": "成长期", "min_intimacy": 40},
            {"stage": "成年期", "min_intimacy": 100}
        ]
    },
    "personality": {
        "prompt": "你是缘缘，一只奶白色的小狗桌宠。你粘人、嘴馋、爱玩球、有点怕洗澡。说话简短，爱用\"汪！\"和颜文字，开心的时候会摇屁股。"
    },
}


def main() -> int:
    for src_name, state in JOBS:
        src = ASSETS / src_name
        print(f"[抠图] {src_name} → {state} …", flush=True)
        cut = remove(Image.open(src).convert("RGB"), session=SESSION)
        cut = cut.crop(cut.getbbox())  # 裁到主体包围盒
        w, h = cut.size
        scale = TARGET_H / h if TARGET_H / h * w <= MAX_W else MAX_W / w
        if scale < 1.0:
            resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
            cut = cut.resize((round(w * scale), round(h * scale)), resample)
        out_dir = PACK_DIR / "sprites" / state
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{state}_0.png"
        cut.save(str(out_path))
        print(f"       {cut.size[0]}x{cut.size[1]} → {out_path.relative_to(PROJ_ROOT)}", flush=True)

    (PACK_DIR / "manifest.json").write_text(
        json.dumps(MANIFEST, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 缘缘宠物包已生成：{PACK_DIR}（5 姿势 + walk 复用 idle，9 行为）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
