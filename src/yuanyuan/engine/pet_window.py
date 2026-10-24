"""透明置顶宠物窗口（T1.6 拖拽/物理 + T1.7 右键菜单）+ 呼吸/摇摆微动画 + 行走"""

from __future__ import annotations

import math
import time

from PyQt6.QtCore import QPoint, QPointF, Qt, QTimer
from PyQt6.QtGui import QAction, QPainter
from PyQt6.QtWidgets import QMenu, QWidget

from ..content.models import PetPack
from .animator import StateMachine
from .physics import VerticalPhysics

DRAG_THRESHOLD = 6  # px；超过视为拖拽而非点击


class PetWindow(QWidget):
    def __init__(self, pack: PetPack, sm: StateMachine):
        super().__init__()
        self.pack = pack
        self.sm = sm
        self._drag_offset: QPoint | None = None
        self._press_pos: QPoint | None = None
        self._moved = False
        self._walk_dir = 1
        self._t0 = time.monotonic()
        self._floor_bottom_y = 0.0  # 本窗口坐标系的地面 y（窗口高 = 站立高度）

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 窗口尺寸 = 所有状态帧的最大尺寸（缩放后）
        pixmaps = [pm for frames in sm.pixmaps.values() for pm in frames]
        self.resize(max(pm.width() for pm in pixmaps), max(pm.height() for pm in pixmaps))
        self._floor_bottom_y = float(self.height())

        self._physics = VerticalPhysics()
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start(33)  # ~30fps

    # ---- 布局 ----
    def place_on(self, screen) -> None:
        """开机：从屏幕顶上方掉落，落到任务栏上沿。screen 为 QScreen。"""
        self._screen = screen
        geo = screen.geometry()
        self.move(geo.left() + int(geo.width() * 0.62), geo.top() - self.height())
        self._physics.drop()

    # ---- 主循环 ----
    def _tick(self) -> None:
        # 物理下落
        if self._physics.mode == "falling":
            geo = self._screen.availableGeometry()
            target_bottom = geo.bottom() + 1
            # 把窗口坐标系的 floor 折算给 physics：physics 直接操作窗口 bottom 全局值
            bottom_global = self.y() + self.height()
            bottom_new = self._physics.update(bottom_global, float(target_bottom))
            self.move(self.x(), int(bottom_new - self.height()))
        else:
            # 行走：当前状态带 movement.speed 时水平位移
            state = self.pack.states[self.sm.current]
            if state.speed:
                geo = self._screen.availableGeometry()
                x = self.x() + int(self._walk_dir * state.speed * 0.033)
                if x < geo.left() or x + self.width() > geo.right() + 1:
                    self._walk_dir *= -1
                    x = max(geo.left(), min(x, geo.right() + 1 - self.width()))
                self.move(x, self.y())
        self.update()

    # ---- 绘制：锚点 bottom_center + 呼吸 + 移动时摇摆 ----
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        pm = self.sm.current_pixmap()
        t = time.monotonic() - self._t0
        state = self.pack.states[self.sm.current]
        breathe = 1.0 + 0.025 * math.sin(2 * math.pi * t / 3.0)
        tilt = 3.0 * math.sin(2 * math.pi * t / 1.6) if state.speed else 0.0

        cx = self.width() / 2
        bottom = self._floor_bottom_y
        painter.translate(cx, bottom)
        painter.rotate(tilt)
        painter.scale(1.0, breathe)
        painter.drawPixmap(QPointF(-pm.width() / 2, -pm.height()), pm)

    # ---- 鼠标：点击 / 双击 / 拖拽 ----
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._press_pos = e.globalPosition().toPoint()
            self._moved = False

    def mouseMoveEvent(self, e) -> None:
        if self._press_pos is None:
            return
        delta = e.globalPosition().toPoint() - self._press_pos
        if not self._moved and delta.manhattanLength() > DRAG_THRESHOLD:
            self._moved = True
            self._physics.mode = "rest"
            self.sm.on_event("drag_start")
        if self._moved:
            self.move(e.globalPosition().toPoint() - QPoint(self.width() // 2, self.height() - 8))

    def mouseReleaseEvent(self, e) -> None:
        if e.button() != Qt.MouseButton.LeftButton or self._press_pos is None:
            return
        self._press_pos = None
        if self._moved:
            self._moved = False
            self.sm.on_event("drag_end")
            self._physics.drop()  # 松手 → 从当前位置掉落
        else:
            self.sm.on_event("click")

    def mouseDoubleClickEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.sm.on_event("double_click")

    # ---- 右键菜单（T1.7；喂食/静默/设置为占位）----
    def contextMenuEvent(self, _event) -> None:
        menu = QMenu(self)
        for label in ("喂食（M2）", "静默模式（M3）", "设置（M5）"):
            act = QAction(label, menu)
            act.setEnabled(False)
            menu.addAction(act)
        menu.addSeparator()
        menu.addAction(QAction("退出", menu)).triggered.connect(self._quit)
        menu.exec(self.mapToGlobal(QPoint(self.width() // 2, 0)))

    def _quit(self) -> None:
        self._anim_timer.stop()
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()
