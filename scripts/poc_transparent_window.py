"""T1.2 透明置顶窗口 PoC —— M1 性能关卡（PRD 假设 A1 验证）

验证点：
1. 无边框 + 透明背景 + 始终置顶窗口能否创建并正常渲染
2. 多显示器 / DPI 信息采集
3. 拖拽移动代码路径可用
4. 30fps 呼吸动画（空闲状态最坏情况）下的 CPU / 内存是否达标（整机 CPU < 1%，内存 < 150MB）
5. 窗口自截图存档，供人工核验透明与置顶效果

运行后窗口出现 12 秒，自动关闭并打印报告。

用法：python scripts/poc_transparent_window.py
"""

import math
import sys
import time
from pathlib import Path

import psutil
from PyQt6.QtCore import QT_VERSION_STR, QPointF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QPainter, QRadialGradient
from PyQt6.QtWidgets import QApplication, QWidget

SHOW_SECONDS = 12.0
SCRIPT_DIR = Path(__file__).resolve().parent


class PetBlob(QWidget):
    """最小宠物实体：一个会呼吸的奶白色圆团 + 眼睛（缘缘剪影占位）。"""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(160, 160)
        self._t0 = time.monotonic()
        self._drag_offset = None
        # 30fps 重绘：衡量空闲 CPU 的最坏情况
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self.update)
        self._anim_timer.start(33)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = time.monotonic() - self._t0
        breathe = 1.0 + 0.03 * math.sin(2 * math.pi * t / 3.0)
        sway = 2.0 * math.sin(2 * math.pi * t / 7.0)  # ±2° 待机摇摆的位移模拟
        cx, cy = self.width() / 2 + sway, self.height() / 2
        w, h = self.width() * breathe, self.height() * breathe

        body = QRadialGradient(QPointF(cx, cy + h * 0.1), w * 0.45)
        body.setColorAt(0.0, QColor(255, 250, 240))
        body.setColorAt(1.0, QColor(238, 224, 200))
        painter.setBrush(QBrush(body))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), w * 0.40, h * 0.36)

        painter.setBrush(QColor(60, 45, 40))
        eye_dx, eye_dy = w * 0.13, h * 0.08
        painter.drawEllipse(QPointF(cx - eye_dx, cy - eye_dy), w * 0.045, h * 0.06)
        painter.drawEllipse(QPointF(cx + eye_dx, cy - eye_dy), w * 0.045, h * 0.06)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_offset is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, _e):
        self._drag_offset = None


def main():
    app = QApplication(sys.argv)
    proc = psutil.Process()
    report = []

    screens = app.screens()
    report.append(f"[环境] PyQt6 (Qt {QT_VERSION_STR}) | Python {sys.version.split()[0]} | 逻辑核 {psutil.cpu_count(logical=True)}")
    report.append(f"[显示器] 共 {len(screens)} 块")
    for i, s in enumerate(screens):
        g, a = s.geometry(), s.availableGeometry()
        report.append(f"  屏幕{i}: {g.width()}x{g.height()} DPR={s.devicePixelRatio()} 可用 {a.width()}x{a.height()}")

    pet = PetBlob()
    geo = screens[0].availableGeometry()
    pet.move(geo.right() - 240, geo.bottom() - 240)
    pet.show()
    flags = pet.windowFlags()
    report.append(
        f"[窗口] 已创建并显示: frameless={bool(flags & Qt.WindowType.FramelessWindowHint)}, "
        f"topmost={bool(flags & Qt.WindowType.WindowStaysOnTopHint)}, "
        f"translucent={pet.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)}"
    )

    def finish():
        cpu_single = proc.cpu_percent(interval=2.0)
        cores = psutil.cpu_count(logical=True) or 1
        cpu_total = cpu_single / cores
        mem_mb = proc.memory_info().rss / 1024 / 1024
        shot_path = SCRIPT_DIR.parent / "docs" / "PoC截图-透明窗口.png"
        pet.grab().save(str(shot_path))
        report.append(f"[性能] 30fps 呼吸动画下：CPU 单核 {cpu_single:.1f}% = 整机 {cpu_total:.2f}%（达标线 <1%：{'✅' if cpu_total < 1.0 else '❌ 需优化'}）")
        report.append(f"[性能] 内存 {mem_mb:.0f} MB（达标线 <150MB：{'✅' if mem_mb < 150 else '❌'}）")
        report.append(f"[截图] 已保存 {shot_path}")
        print("\n".join(report))
        app.quit()

    QTimer.singleShot(int(SHOW_SECONDS * 1000), finish)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
