"""聊天气泡 + 输入条（T4.2 MVP）：置顶无边框小窗，风格与宠物一致。"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

_STYLE = """
    background-color: #FFF8EC;
    color: #3C2D28;
    border: 2px solid #D6C3AA;
    border-radius: 12px;
    padding: 8px 12px;
    font-size: 13px;
"""


class Bubble(QWidget):
    """对话气泡：show_text(text, seconds)；seconds=None 表示停留到下一条。"""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setMaximumWidth(300)
        self._label.setStyleSheet(_STYLE)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_text(self, text: str, seconds: float | None = 12.0) -> None:
        self._label.setText(text)
        self.adjustSize()  # 两次让 word-wrap 的 sizeHint 稳定下来
        self._label.adjustSize()
        self.adjustSize()
        self.show()
        self.raise_()
        if seconds:
            self._hide_timer.start(int(seconds * 1000))
        else:
            self._hide_timer.stop()

    def place_above(self, anchor) -> None:
        """锚在某个窗口（宠物）上方居中"""
        x = anchor.center().x() - self.width() // 2
        y = anchor.top() - self.height() - 10
        self.move(max(0, x), max(0, y))


class ChatInput(QWidget):
    """迷你输入条：回车或按钮发送；Esc 关闭。"""

    send_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._edit = QLineEdit(self)
        self._edit.setPlaceholderText("跟缘缘说点什么…（回车发送，Esc 关闭）")
        self._edit.setFixedWidth(260)
        self._edit.setStyleSheet(_STYLE)
        btn = QPushButton("发送", self)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("background-color:#EEDCB8; color:#3C2D28; border:1px solid #D6C3AA;"
                          "border-radius:8px; padding:6px 12px; font-size:13px;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._edit)
        layout.addWidget(btn)
        self._edit.returnPressed.connect(self._send)
        btn.clicked.connect(self._send)

    def _send(self) -> None:
        text = self._edit.text().strip()
        if text:
            self._edit.clear()
            self.send_requested.emit(text)

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)

    def focus(self) -> None:
        self.show()
        self.raise_()
        self._edit.setFocus()

    def place_above(self, anchor) -> None:
        x = anchor.center().x() - self.width() // 2
        y = anchor.top() - self.height() - 10
        self.move(max(0, x), max(0, y))
