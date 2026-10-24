"""设置界面（T5.3）：AI / 提醒 / 专注 / 大小 / 开机自启，保存即生效。

对话框只做表单；业务落点由 app 通过回调注入（读写 config.json / manifest / reminders / focus）。
"""

from __future__ import annotations

import json

from PyQt6.QtWidgets import (QCheckBox, QDialog, QDoubleSpinBox, QFormLayout,
                             QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QSpinBox, QVBoxLayout)


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
