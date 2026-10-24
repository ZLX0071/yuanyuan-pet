"""T1.3：生成示例宠物包「示例团子」——程序自绘帧，验证整条宠物包管线。

运行：python scripts/make_demo_pack.py
产物：pets/demo-blob/（manifest.json + sprites/）
"""

import json
import sys
from pathlib import Path

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen

PROJ_ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = PROJ_ROOT / "pets" / "demo-blob"
CANVAS = 256


def _blob(painter: QPainter, cx: float, cy: float, rx: float, ry: float,
          eyes: str = "open", tongue: bool = False) -> None:
    body = QColor(248, 238, 220)
    ink = QColor(60, 45, 40)
    painter.setBrush(body)
    painter.setPen(QPen(QColor(215, 198, 172), 2))
    painter.drawEllipse(QPointF(cx, cy), rx, ry)
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


def _frame(draw) -> QImage:
    img = QImage(CANVAS, CANVAS, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw(painter)
    painter.end()
    return img


def main() -> int:
    _app = QGuiApplication(sys.argv)  # noqa: F841  QImage/Painter 需要
    cx, cy, rx, ry = CANVAS / 2, CANVAS * 0.62, CANVAS * 0.30, CANVAS * 0.26

    frames = {
        "sprites/idle/idle_0.png": lambda p: _blob(p, cx, cy, rx, ry, "open", tongue=True),
        "sprites/idle/idle_1.png": lambda p: _blob(p, cx, cy, rx, ry, "blink"),
        "sprites/walk/walk_0.png": lambda p: _blob(p, cx - 10, cy, rx, ry * 0.97, "open"),
        "sprites/walk/walk_1.png": lambda p: _blob(p, cx + 10, cy, rx, ry * 0.97, "open"),
        "sprites/sleep/sleep_0.png": lambda p: (
            _blob(p, cx, cy + 14, rx * 1.08, ry * 0.92, "blink"),
            p.setBrush(QColor(200, 215, 235)),
            p.drawEllipse(QPointF(cx + 40, cy - 60), 7, 7),
            p.drawEllipse(QPointF(cx + 52, cy - 80), 10, 10),
        ),
        "sprites/drag/drag_0.png": lambda p: _blob(p, cx, cy - 8, rx * 0.88, ry * 1.15, "wide"),
        "sprites/alert/alert_0.png": lambda p: (
            _blob(p, cx, cy, rx, ry, "wide"),
            p.setBrush(QColor(235, 120, 100)),
            p.drawEllipse(QPointF(cx + 48, cy - 66), 6, 12),
            p.drawEllipse(QPointF(cx + 48, cy - 46), 4, 4),
        ),
    }
    PACK_DIR.mkdir(parents=True, exist_ok=True)
    for rel, draw in frames.items():
        path = PACK_DIR / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        _frame(draw).save(str(path))

    manifest = {
        "format_version": "1.0",
        "meta": {
            "name": "示例团子",
            "author": "ZCode",
            "version": "0.1.0",
            "description": "验证宠物包管线的程序自绘示例（脚本生成，可随时重新生成）",
            "license": "CC0（本项目自绘）",
        },
        "display": {"scale": 1.0, "anchor": "bottom_center"},
        "default_state": "idle",
        "startup_state": "alert",
        "startup_duration_s": 2.0,
        "states": {
            "idle": {"frames": "sprites/idle/idle_*.png", "fps": 2, "loop": True},
            "walk": {"frames": "sprites/walk/walk_*.png", "fps": 6, "loop": True,
                     "movement": {"speed": 40}},
            "sleep": {"frames": "sprites/sleep/sleep_*.png", "fps": 1, "loop": True},
            "drag": {"frames": "sprites/drag/drag_*.png", "fps": 1, "loop": True},
            "alert": {"frames": "sprites/alert/alert_*.png", "fps": 2, "loop": True},
        },
        "behaviors": [
            {"id": "wander", "from": "idle", "to": "walk",
             "trigger": {"type": "random", "every_s": [20, 90]},
             "duration_s": [3, 8], "interruptible": True},
            {"id": "picked_up", "from": "*", "to": "drag",
             "trigger": {"type": "drag_start"}},
            {"id": "dropped", "from": "drag", "to": "idle",
             "trigger": {"type": "drag_end"}},
            {"id": "nap", "from": "idle", "to": "sleep",
             "trigger": {"type": "idle_time", "s": 300}},
            {"id": "wake", "from": ["sleep", "walk"], "to": "idle",
             "trigger": {"type": "click"}},
            {"id": "greet", "from": "*", "to": "alert",
             "trigger": {"type": "double_click"}, "duration_s": [1.5, 2.5]},
            {"id": "react_typing", "from": "idle", "to": "alert",
             "trigger": {"type": "sense", "event": "typing_burst"}},
        ],
        "personality": {
            "prompt": "你是示例团子，一只圆滚滚的测试用小团子。说话简短。"
        },
    }
    (PACK_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 示例包已生成：{PACK_DIR}（{len(frames)} 帧，5 状态，7 行为）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
