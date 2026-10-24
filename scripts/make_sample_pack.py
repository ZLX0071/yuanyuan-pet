"""T6.4：示例包生成器——一条命令生成一个程序自绘宠物包（CC0，可作创作模板）。

用法示例：
  python scripts/make_sample_pack.py --name 橘团子 --color 240,168,72 --ears round --out pets/orange-blob
  python scripts/make_sample_pack.py --name 长耳团 --color 248,244,235 --ears long --out pets/bunny-blob
"""

import argparse
import json
import sys
from pathlib import Path

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen

PROJ_ROOT = Path(__file__).resolve().parents[1]
CANVAS = 256


def _draw_blob(painter: QPainter, cx, cy, rx, ry, body: QColor, ears: str,
               eyes: str = "open", tongue: bool = False) -> None:
    ink = QColor(60, 45, 40)
    painter.setBrush(body)
    painter.setPen(QPen(QColor(max(0, body.red() - 35), max(0, body.green() - 35),
                               max(0, body.blue() - 35)), 2))
    if ears == "long":  # 长耳（兔系）
        for dx in (-rx * 0.45, rx * 0.45):
            painter.drawEllipse(QPointF(cx + dx, cy - ry * 0.95), rx * 0.22, ry * 0.5)
    painter.drawEllipse(QPointF(cx, cy), rx, ry)
    if ears == "round":  # 圆耳（熊系）
        for dx in (-rx * 0.6, rx * 0.6):
            painter.drawEllipse(QPointF(cx + dx, cy - ry * 0.85), rx * 0.18, ry * 0.18)
    painter.setBrush(ink)
    painter.setPen(Qt.PenStyle.NoPen)
    dx, dy = rx * 0.32, ry * 0.22
    if eyes == "open":
        painter.drawEllipse(QPointF(cx - dx, cy - dy), rx * 0.10, ry * 0.13)
        painter.drawEllipse(QPointF(cx + dx, cy - dy), rx * 0.10, ry * 0.13)
    elif eyes == "wide":
        painter.drawEllipse(QPointF(cx - dx, cy - dy), rx * 0.13, ry * 0.17)
        painter.drawEllipse(QPointF(cx + dx, cy - dy), rx * 0.13, ry * 0.17)
    else:  # blink
        painter.setPen(QPen(ink, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(cx - dx - 5, cy - dy), QPointF(cx - dx + 5, cy - dy))
        painter.drawLine(QPointF(cx + dx - 5, cy - dy), QPointF(cx + dx + 5, cy - dy))
        painter.setPen(Qt.PenStyle.NoPen)
    if tongue:
        painter.setBrush(QColor(240, 170, 170))
        painter.drawEllipse(QPointF(cx, cy + ry * 0.35), rx * 0.12, ry * 0.10)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成程序自绘示例宠物包")
    parser.add_argument("--name", required=True, help="宠物名")
    parser.add_argument("--color", default="248,238,220", help="身体颜色 R,G,B")
    parser.add_argument("--ears", default="round", choices=["round", "long", "none"])
    parser.add_argument("--out", required=True, help="输出目录（pets/ 下的文件夹名）")
    args = parser.parse_args()

    _app = QGuiApplication(sys.argv)  # noqa: F841
    r, g, b = (int(x) for x in args.color.split(","))
    body = QColor(r, g, b)
    out_dir = PROJ_ROOT / "pets" / args.out
    cx, cy, rx, ry = CANVAS / 2, CANVAS * 0.62, CANVAS * 0.30, CANVAS * 0.26

    def frame(draw) -> QImage:
        img = QImage(CANVAS, CANVAS, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw(p)
        p.end()
        return img

    frames = {
        "sprites/idle/idle_0.png": lambda p: _draw_blob(p, cx, cy, rx, ry, body, args.ears, "open", True),
        "sprites/idle/idle_1.png": lambda p: _draw_blob(p, cx, cy, rx, ry, body, args.ears, "blink"),
        "sprites/walk/walk_0.png": lambda p: _draw_blob(p, cx - 10, cy, rx, ry * 0.97, body, args.ears, "open"),
        "sprites/walk/walk_1.png": lambda p: _draw_blob(p, cx + 10, cy, rx, ry * 0.97, body, args.ears, "open"),
        "sprites/sleep/sleep_0.png": lambda p: (
            _draw_blob(p, cx, cy + 14, rx * 1.08, ry * 0.92, body, args.ears, "blink"),
            p.setBrush(QColor(200, 215, 235)),
            p.drawEllipse(QPointF(cx + 40, cy - 60), 7, 7),
            p.drawEllipse(QPointF(cx + 52, cy - 80), 10, 10),
        ),
        "sprites/drag/drag_0.png": lambda p: _draw_blob(p, cx, cy - 8, rx * 0.88, ry * 1.15, body, args.ears, "wide"),
        "sprites/excited/excited_0.png": lambda p: _draw_blob(p, cx, cy - 4, rx, ry * 1.05, body, args.ears, "wide", True),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    for rel, draw in frames.items():
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        frame(draw).save(str(path))

    manifest = {
        "format_version": "1.0",
        "meta": {"name": args.name, "author": "you", "version": "1.0.0",
                 "description": f"程序自绘示例包「{args.name}」（模板生成，可自由改造）",
                 "license": "CC0"},
        "display": {"scale": 1.0, "anchor": "bottom_center"},
        "default_state": "idle",
        "startup_state": "excited",
        "startup_duration_s": 2.0,
        "states": {
            "idle": {"frames": "sprites/idle/idle_*.png", "fps": 2, "loop": True},
            "walk": {"frames": "sprites/walk/walk_*.png", "fps": 6, "loop": True,
                     "movement": {"speed": 40}},
            "sleep": {"frames": "sprites/sleep/sleep_*.png", "fps": 1, "loop": True},
            "drag": {"frames": "sprites/drag/drag_*.png", "fps": 1, "loop": True},
            "excited": {"frames": "sprites/excited/excited_*.png", "fps": 2, "loop": True},
        },
        "behaviors": [
            {"id": "wander", "from": "idle", "to": "walk",
             "trigger": {"type": "random", "every_s": [20, 90]}, "duration_s": [3, 8]},
            {"id": "picked_up", "from": "*", "to": "drag", "trigger": {"type": "drag_start"}},
            {"id": "dropped", "from": "drag", "to": "idle", "trigger": {"type": "drag_end"}},
            {"id": "nap", "from": "idle", "to": "sleep",
             "trigger": {"type": "idle_time", "s": 300}},
            {"id": "wake", "from": ["sleep", "walk"], "to": "idle", "trigger": {"type": "click"}},
            {"id": "greet", "from": "*", "to": "excited",
             "trigger": {"type": "double_click"}, "duration_s": [1.5, 2.5]},
        ],
        "life": {
            "decay_per_hour": {"hunger": 4.0, "mood": 3.0},
            "interactions": {
                "feed": {"hunger": 35, "mood": 12, "intimacy": 1, "state": "excited", "duration_s": 3},
                "pet": {"mood": 6, "intimacy": 1, "state": "excited", "duration_s": 2}
            },
            "growth": [{"stage": "幼年期", "min_intimacy": 0, "scale": 0.85},
                       {"stage": "成长期", "min_intimacy": 40, "scale": 0.95},
                       {"stage": "成年期", "min_intimacy": 100, "scale": 1.05}]
        },
        "sense": {"reminders": {
            "water": {"every_min": 45, "message": f"汪！{args.name}陪你去接杯水嘛…"},
            "rest": {"every_min": 60, "message": "盯屏幕很久啦，站起来伸个懒腰！"}}},
        "personality": {"prompt": f"你是{args.name}，一只圆滚滚的小团子桌宠。说话简短爱撒娇。"}
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 示例包已生成：{out_dir}（{len(frames)} 帧，5 状态，6 行为，格式 v1.0）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
