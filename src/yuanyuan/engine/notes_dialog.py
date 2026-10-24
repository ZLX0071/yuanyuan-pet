"""我的记事管理窗（P0-2）：列表 + 完成/删除。"""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget, QHBoxLayout


class NotesDialog(QDialog):
    """ctx: get_notes() -> list[dict]  on_done(id)  on_delete(id)"""

    def __init__(self, ctx: dict, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("我的记事 · 缘缘帮你记着")
        self.setMinimumWidth(380)
        self.root = QVBoxLayout(self)
        self.refresh()

    def refresh(self) -> None:
        while self.root.count():
            item = self.root.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        notes = self.ctx["get_notes"]()
        if not notes:
            empty = QLabel("（现在没有待办的记事哦——对缘缘说\"记一下…\"就能添加）")
            empty.setWordWrap(True)
            self.root.addWidget(empty)
        for n in notes:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            text = QLabel(n["text"] + (f"　⏰ {n['due']}" if n.get("due") else ""))
            text.setWordWrap(True)
            btn_done = QPushButton("完成")
            btn_del = QPushButton("删除")
            btn_done.clicked.connect(lambda _=False, i=n["id"]: self._act("on_done", i))
            btn_del.clicked.connect(lambda _=False, i=n["id"]: self._act("on_delete", i))
            h.addWidget(text, 1)
            h.addWidget(btn_done)
            h.addWidget(btn_del)
            self.root.addWidget(row)
        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        self.root.addWidget(close)

    def _act(self, key: str, note_id: str) -> None:
        self.ctx[key](note_id)
        self.refresh()
