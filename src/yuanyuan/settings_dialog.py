"""设置界面（T5.3）：AI / 提醒 / 专注 / 大小 / 开机自启，保存即生效。

对话框只做表单；业务落点由 app 通过回调注入（读写 config.json / manifest / reminders / focus）。
"""

from __future__ import annotations

import json
import re

from PyQt6.QtCore import QTime
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
                             QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QSpinBox, QTableWidget, QTableWidgetItem, QTimeEdit,
                             QVBoxLayout)


class SettingsDialog(QDialog):
    """ctx 回调约定（app 提供）：
    ai_cfg: dict | None            当前 AI 配置（含 api_key）
    save_ai_cfg(cfg)               持久化并热替换 provider
    reminders                      ReminderScheduler（直接改 items）
    get_focus_min() / set_focus_min(m)
    get_scale() / apply_scale(s)   更新 pack.scale + manifest + 重建 pixmap
    autostart_cmd() -> str         自启命令行
    """

    def __init__(self, ctx: dict, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("缘缘 · 设置")
        self.setMinimumWidth(420)
        root = QVBoxLayout(self)

        # ---- AI ----
        gb_ai = QGroupBox("AI 服务（OpenAI 兼容）")
        form_ai = QFormLayout(gb_ai)
        ai = (self.ctx["ai_cfg"]() or {})
        self.ed_base = QLineEdit(str(ai.get("base_url", "")))
        self.ed_key = QLineEdit(str(ai.get("api_key", "")))
        self.ed_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ed_model = QLineEdit(str(ai.get("model", "")))
        self.sp_budget = QSpinBox()
        self.sp_budget.setRange(1, 100_000_000)
        self.sp_budget.setSingleStep(100_000)
        self.sp_budget.setValue(int(ai.get("monthly_token_budget", 2_000_000)))
        form_ai.addRow("服务地址", self.ed_base)
        form_ai.addRow("API Key", self.ed_key)
        form_ai.addRow("模型", self.ed_model)
        form_ai.addRow("月度 token 额度", self.sp_budget)
        btn_test = QPushButton("测试连接")
        btn_test.clicked.connect(self._test_connection)
        form_ai.addRow("", btn_test)
        root.addWidget(gb_ai)

        # ---- 提醒 ----
        gb_rem = QGroupBox("提醒")
        form_rem = QFormLayout(gb_rem)
        self.rem_widgets = {}
        for kind, label in (("water", "喝水提醒"), ("rest", "久坐提醒")):
            item = self.ctx["reminders"].items[kind]
            cb = QCheckBox("开启")
            cb.setChecked(bool(item.get("enabled", True)))
            sp = QSpinBox()
            sp.setRange(5, 720)
            sp.setValue(int(item.get("every_min", 45)))
            sp.setSuffix(" 分钟")
            row = QHBoxLayout()
            row.addWidget(cb)
            row.addWidget(sp)
            form_rem.addRow(label, row)
            self.rem_widgets[kind] = (cb, sp)
        root.addWidget(gb_rem)

        # ---- 免打扰时段（P0-3）----
        gb_dnd = QGroupBox("免打扰时段（期间提醒静默，过后补上）")
        row_dnd = QHBoxLayout(gb_dnd)
        self.cb_dnd = QCheckBox("启用")
        dnd = self.ctx["get_dnd"]()
        self.cb_dnd.setChecked(bool(dnd.get("enabled", False)))
        self.te_start = QTimeEdit()
        self.te_end = QTimeEdit()
        self.te_start.setDisplayFormat("HH:mm")
        self.te_end.setDisplayFormat("HH:mm")

        def _qtime(text: str, fallback: str) -> QTime:
            try:
                return QTime.fromString(str(text or fallback), "HH:mm")
            except Exception:
                return QTime.fromString(fallback, "HH:mm")

        self.te_start.setTime(_qtime(dnd.get("start"), "23:00"))
        self.te_end.setTime(_qtime(dnd.get("end"), "08:00"))
        row_dnd.addWidget(self.cb_dnd)
        row_dnd.addWidget(QLabel("从"))
        row_dnd.addWidget(self.te_start)
        row_dnd.addWidget(QLabel("到"))
        row_dnd.addWidget(self.te_end)
        row_dnd.addStretch(1)
        root.addWidget(gb_dnd)

        # ---- 作息还原（X1）----
        gb_sched = QGroupBox("作息还原（缘缘按你的节奏自主生活）")
        v_sched = QVBoxLayout(gb_sched)
        sched = self.ctx["get_schedule"]()
        self.cb_sched = QCheckBox("启用作息还原")
        self.cb_sched.setChecked(bool(sched.get("enabled", False)))
        v_sched.addWidget(self.cb_sched)
        self.table_sched = QTableWidget(0, 4)
        self.table_sched.setHorizontalHeaderLabels(["时间 HH:MM", "动作", "说明", "持续秒(空=到互动)"])
        self.table_sched.setMaximumHeight(170)
        self._sched_states = self.ctx["pack_states"]
        v_sched.addWidget(self.table_sched)
        row_btns = QHBoxLayout()
        for text, fn in (("添加一行", self._add_sched_row), ("删除选中", self._del_sched_row),
                         ("填入示例", self._sample_sched)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row_btns.addWidget(b)
        row_btns.addStretch(1)
        v_sched.addLayout(row_btns)
        for e in (sched.get("entries") or []):
            self._add_sched_row(e)
        root.addWidget(gb_sched)

        # ---- 专注 / 大小 ----
        gb_fd = QGroupBox("专注与体型")
        form_fd = QFormLayout(gb_fd)
        self.sp_focus = QSpinBox()
        self.sp_focus.setRange(5, 120)
        self.sp_focus.setValue(int(self.ctx["get_focus_min"]()))
        self.sp_focus.setSuffix(" 分钟")
        form_fd.addRow("专注时长", self.sp_focus)
        self.sp_scale = QDoubleSpinBox()
        self.sp_scale.setRange(0.2, 1.0)
        self.sp_scale.setSingleStep(0.02)
        self.sp_scale.setDecimals(2)
        self.sp_scale.setValue(float(self.ctx["get_scale"]()))
        form_fd.addRow("体型倍率", self.sp_scale)
        root.addWidget(gb_fd)

        # ---- 自启 ----
        self.cb_autostart = QCheckBox("开机自动启动缘缘")
        self.cb_autostart.setChecked(self.ctx["get_autostart"]())
        root.addWidget(self.cb_autostart)

        hint = QLabel("AI 配置保存在 data/config.json（本地文件，不上传）；记事与存档全部只存本地。")
        hint.setWordWrap(True)
        root.addWidget(hint)

        buttons = QHBoxLayout()
        btn_save = QPushButton("保存并应用")
        btn_cancel = QPushButton("取消")
        btn_save.clicked.connect(self._save)
        btn_cancel.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(btn_cancel)
        buttons.addWidget(btn_save)
        root.addLayout(buttons)

    # ---- 作息表编辑（X1）----
    def _add_sched_row(self, entry: dict | None = None) -> None:
        entry = entry or {}
        row = self.table_sched.rowCount()
        self.table_sched.insertRow(row)
        self.table_sched.setItem(row, 0, QTableWidgetItem(str(entry.get("time", "08:00"))))
        combo = QComboBox()
        combo.addItems(self._sched_states)
        state = str(entry.get("state", "idle"))
        combo.setCurrentText(state if state in self._sched_states else "idle")
        self.table_sched.setCellWidget(row, 1, combo)
        self.table_sched.setItem(row, 2, QTableWidgetItem(str(entry.get("label", ""))))
        dur = entry.get("duration_s")
        self.table_sched.setItem(row, 3, QTableWidgetItem("" if dur in (None, "") else str(int(dur))))

    def _del_sched_row(self) -> None:
        for r in sorted({i.row() for i in self.table_sched.selectedIndexes()}, reverse=True):
            self.table_sched.removeRow(r)

    def _sample_sched(self) -> None:
        from yuanyuan.life.schedule import DEFAULT_SCHEDULE
        self.table_sched.setRowCount(0)
        for e in DEFAULT_SCHEDULE["entries"]:
            self._add_sched_row(e)
        self.cb_sched.setChecked(True)

    def _collect_sched(self) -> dict | None:
        """收集作息表；时间格式错误返回 None。"""
        entries = []
        for r in range(self.table_sched.rowCount()):
            t_item = self.table_sched.item(r, 0)
            t = (t_item.text().strip() if t_item else "")
            if not t:
                continue
            if not re.match(r"^\d{1,2}:\d{2}$", t):
                return None
            combo = self.table_sched.cellWidget(r, 1)
            label_item = self.table_sched.item(r, 2)
            dur_item = self.table_sched.item(r, 3)
            dur_txt = (dur_item.text().strip() if dur_item else "")
            entries.append({
                "time": t.zfill(5),
                "state": combo.currentText() if combo else "idle",
                "label": label_item.text().strip() if label_item else "",
                "duration_s": float(dur_txt) if dur_txt else None,
            })
        return {"enabled": self.cb_sched.isChecked(), "entries": entries}

    def _test_connection(self) -> None:
        base, key, model = self.ed_base.text().strip(), self.ed_key.text().strip(), self.ed_model.text().strip()
        try:
            from yuanyuan.ai.provider import Provider
            cfg = {"base_url": base, "api_key": key, "model": model,
                   "max_tokens": 50, "timeout_s": 30}
            reply, tokens = Provider(cfg).chat(
                [{"role": "user", "content": "回复：OK"}])
            QMessageBox.information(self, "连接成功", f"模型 {model} 回复：{reply[:40]}\n（{tokens} tokens）")
        except Exception as e:  # noqa: BLE001 对话框内直接展示
            QMessageBox.warning(self, "连接失败", str(e))

    def _save(self) -> None:
        # 免打扰（P0-3）
        self.ctx["save_dnd"]({
            "enabled": self.cb_dnd.isChecked(),
            "start": self.te_start.time().toString("HH:mm"),
            "end": self.te_end.time().toString("HH:mm"),
        })
        # 作息（X1）
        sched = self._collect_sched()
        if sched is None:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "格式错误", "作息表的时间格式应为 HH:MM（如 07:30）")
            return
        self.ctx["save_schedule"](sched)
        # AI
        ai_cfg = {
            "base_url": self.ed_base.text().strip(),
            "api_key": self.ed_key.text().strip(),
            "model": self.ed_model.text().strip() or "gpt-4o-mini",
            "max_tokens": 1000,
            "monthly_token_budget": self.sp_budget.value(),
            "timeout_s": 60,
        }
        self.ctx["save_ai_cfg"](ai_cfg)
        # 提醒
        for kind, (cb, sp) in self.rem_widgets.items():
            item = self.ctx["reminders"].items[kind]
            item["enabled"] = cb.isChecked()
            item["every_min"] = sp.value()
            item["every_s"] = sp.value() * 60
            item["next"] = self.ctx["now"]() + item["every_s"]
        # 专注
        self.ctx["set_focus_min"](self.sp_focus.value())
        # 大小（写回宠物包 manifest，创作者即用户）
        if abs(self.sp_scale.value() - self.ctx["get_scale"]()) > 1e-6:
            self.ctx["apply_scale"](self.sp_scale.value())
        # 自启
        self.ctx["set_autostart"](self.cb_autostart.isChecked())
        self.accept()
