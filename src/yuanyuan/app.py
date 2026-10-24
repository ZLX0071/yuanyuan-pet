"""组装层：加载宠物包 → 状态机 → 宠物窗口（含托盘与 smoke 模式）"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QAction, QGuiApplication, QIcon, QPixmap, QPainter, QColor
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from yuanyuan.content.models import PetPack
from yuanyuan.content.pack_loader import PackError, load_pack
from yuanyuan.engine.animator import StateMachine
from yuanyuan.engine.pet_window import PetWindow

PROJ_ROOT = Path(__file__).resolve().parents[2]


def _tray_icon_pixmap() -> QPixmap:
    """托盘图标：40x40 奶白圆团（与 PoC 同款画风）"""
    pm = QPixmap(40, 40)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(248, 238, 220))
    p.setPen(QColor(210, 195, 170))
    p.drawEllipse(4, 6, 32, 30)
    p.setBrush(QColor(60, 45, 40))
    p.setPen(QColor(60, 45, 40))
    p.drawEllipse(13, 17, 4, 6)
    p.drawEllipse(23, 17, 4, 6)
    p.end()
    return pm


def _make_tray(app: QApplication, window: PetWindow) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(QIcon(_tray_icon_pixmap()), app)
    tray.setToolTip(f"缘缘桌宠 · {window.pack.name}")
    menu = QMenu()
    info = menu.addAction(f"{window.pack.name}（M1）")
    info.setEnabled(False)
    menu.addSeparator()
    for label in ("喂食（M2）", "静默模式（M3）", "设置（M5）"):
        act = menu.addAction(label)
        act.setEnabled(False)
    menu.addSeparator()
    quit_act = menu.addAction("退出")
    tray.setContextMenu(menu)
    quit_act.triggered.connect(app.quit)
    tray.show()
    return tray


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="缘缘桌宠")
    default_pack = PROJ_ROOT / "pets"
    packs = sorted(d for d in default_pack.iterdir() if d.is_dir()) if default_pack.is_dir() else []
    parser.add_argument("--pack", type=Path, default=packs[0] if packs else None,
                        help="宠物包目录（默认取 pets/ 下第一个）")
    parser.add_argument("--smoke", type=float, default=0.0,
                        help="冒烟测试：运行 N 秒后自动退出并截图")
    args = parser.parse_args(argv)
    if args.pack is None:
        print("pets/ 下没有宠物包。先运行 scripts/make_demo_pack.py 生成示例包。")
        return 1

    # 加载包（人话报错）
    try:
        pack: PetPack = load_pack(args.pack)
    except PackError as e:
        print(f"❌ 宠物包加载失败：{e}")
        return 1
    print(pack.summary())
    for w in pack.warnings:
        print(f"⚠ {w}")

    app = QApplication(argv)
    app.setQuitOnLastWindowClosed(False)

    pixmaps = {
        name: [QPixmap(str(p)) for p in st.frame_paths]
        for name, st in pack.states.items()
    }
    sm = StateMachine(pack, pixmaps)
    sm.state_changed.connect(lambda old, new: print(f"[状态] {old} → {new}", flush=True))
    window = PetWindow(pack, sm)
    window.place_on(app.primaryScreen())
    window.show()
    _make_tray(app, window)
    print(f"[缘缘] 「{pack.name}」已上桌：拖拽 / 双击互动 / 右键菜单 / 托盘退出", flush=True)

    if args.smoke > 0:
        def finish_smoke() -> None:
            shot_dir = PROJ_ROOT / "docs"
            shot_dir.mkdir(exist_ok=True)
            path = shot_dir / f"演示截图-{pack.name}.png"
            window.grab().save(str(path))
            print(f"[smoke] {args.smoke}s 运行结束，状态轨迹见上方日志，截图 {path}")
            app.quit()
        QTimer.singleShot(int(args.smoke * 1000), finish_smoke)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
