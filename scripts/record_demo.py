"""演示视频录制：启动 --demo 编排 → 采集主屏 → 加中文字幕卡 → H.264 MP4。

运行：python scripts/record_demo.py [--seconds 50]
产物：dist/缘缘演示视频.mp4（可直接传 B 站；鼠标光标不在画面中，解说请后期配音）
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

import imageio.v2 as imageio
import mss
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PROJ_ROOT = Path(__file__).resolve().parents[1]
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
]
W, H = 1280, 720


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def card(lines: list[tuple[str, int]], bg=(30, 26, 24)) -> np.ndarray:
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    total = sum(size + 18 for _, size in lines)
    y = (H - total) // 2
    for text, size in lines:
        font = _font(size)
        bbox = d.textbbox((0, 0), text, font=font)
        d.text(((W - (bbox[2] - bbox[0])) // 2, y), text, fill=(248, 238, 220), font=font)
        y += size + 18
    # 角标
    small = _font(18)
    d.text((24, H - 36), "缘缘桌宠 · yuanyuan-pet", fill=(150, 138, 124), font=small)
    return np.array(img)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=50.0)
    args = parser.parse_args()

    out_dir = PROJ_ROOT / "dist"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "缘缘演示视频.mp4"

    chat_msg = "汪！给大家介绍一下我呀～我现在饱饱的！"
    proc = subprocess.Popen([
        str(PROJ_ROOT / ".venv" / "Scripts" / "python.exe"),
        str(PROJ_ROOT / "main.py"),
        "--pack", str(PROJ_ROOT / "pets" / "yuanyuan"),
        "--smoke", str(args.seconds - 4),
        "--demo", "--test-chat", chat_msg,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"[录制] 缘缘演示进程已启动（{args.seconds - 4:.0f}s），2s 后开录…", flush=True)
    time.sleep(2.0)

    writer = imageio.get_writer(str(out_path), fps=30, codec="libx264",
                                quality=8, pixelformat="yuv420p",
                                macro_block_size=None)
    # 片头 2.5s
    head = card([("缘缘桌宠", 88), ("30 秒认识一只会陪你的桌面小狗", 34),
                 ("开源 · 本地优先 · 人人可创作", 26)])
    for _ in range(75):
        writer.append_data(head)

    monitor = {"top": 0, "left": 0, "width": 1920, "height": 1080}
    n_frames = int((args.seconds - 4) * 30)
    with mss.mss() as sct:
        for i in range(n_frames):
            shot = sct.grab(monitor)
            frame = np.asarray(shot)[:, :, :3]  # BGRA→BGR
            frame = np.array(Image.fromarray(frame).resize((W, H), Image.LANCZOS))
            writer.append_data(frame)
            if i % 300 == 0:
                print(f"[录制] {i / 30:.0f}s / {n_frames / 30:.0f}s", flush=True)

    # 片尾 3s
    tail = card([("你的桌宠，10 分钟就能做出来", 44),
                 ("GitHub: ZLX0071/yuanyuan-pet", 30),
                 ("创作指南见仓库 docs/创作指南.md", 24)])
    for _ in range(90):
        writer.append_data(tail)

    writer.close()
    proc.wait(timeout=30)
    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"✅ 视频已生成：{out_path}（{size_mb:.1f} MB，约 {args.seconds + 1.5:.0f}s）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
