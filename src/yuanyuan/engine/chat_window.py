"""独立聊天窗口（P1-2）：滚动历史 + 输入框；与气泡并存（窗口开着时气泡不重复弹）。"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QTextCursor
from PyQt6.QtWidgets import (QHBoxLayout, QLineEdit, QPushButton, QTextEdit,
                             QVBoxLayout, QWidget)

_STYLE = """
QTextEdit { background-color: #FFF8EC; color: #3C2D28; border: 2px solid #D6C3AA;
            border-radius: 10px; padding: 8px; font-size: 13px; }
QLineEdit { background-color: #FFF8EC; color: #3C2D28; border: 2px solid #D6C3AA;
            border-radius: 10px; padding: 6px 10px; font-size: 13px; }
QPushButton { background-color: #EEDCB8; color: #3C2D28; border: 1px solid #D6C3AA;
              border-radius: 8px; padding: 6px 14px; font-size: 13px; }
"""


class ChatWindow(QWidget):
    send_requested = pyqtSignal(str)

    def __init__(self, pet_name: str = "缘缘"):
        super().__init__()
        self.pet_name = pet_name
        self.setWindowTitle(f"和{pet_name}聊天")
        self.resize(380, 480)
        self.setStyleSheet(_STYLE)
        self.setWindowFlags(Qt.WindowType.Window
                            | Qt.WindowType.WindowStaysOnTopHint)

        self.view = QTextEdit(self)
        self.view.setReadOnly(True)
        self.edit = QLineEdit(self)
        self.edit.setPlaceholderText("说点什么…（回车发送）")
        btn = QPushButton("发送")
        row = QHBoxLayout()
        row.addWidget(self.edit, 1)
        row.addWidget(btn)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.addWidget(self.view, 1)
        root.addLayout(row)

        self.edit.returnPressed.connect(self._send)
        btn.clicked.connect(self._send)

    def _send(self) -> None:
        text = self.edit.text().strip()
        if text:
            self.edit.clear()
            self.send_requested.emit(text)

    def append(self, who: str, text: str) -> None:
        name = "我" if who == "user" else self.pet_name
        color = "#6B5B4E" if who == "user" else "#B4713C"
        safe = text.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        self.view.append(f'<span style="color:{color}"><b>{name}</b>：{safe}</span>')
        self.view.moveCursor(QTextCursor.MoveOperation.End)

    def load_history(self, history: list[dict]) -> None:
        self.view.clear()
        for m in history[-40:]:
            role = "user" if m.get("role") == "user" else "pet"
            self.append(role, str(m.get("content", "")))
