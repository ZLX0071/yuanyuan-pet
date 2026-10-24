"""组装层：加载宠物包 → 养成层 → 状态机 → 宠物窗口（含托盘/交互/smoke 模式）"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from yuanyuan.content.models import PetPack
from yuanyuan.content.pack_loader import PackError, load_pack
from yuanyuan.engine.animator import StateMachine
from yuanyuan.engine.pet_window import PetWindow
from yuanyuan.life.save import Save
from yuanyuan.life.stats import Evolution

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


def _make_tray(app: QApplication, actions: dict) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(QIcon(_tray_icon_pixmap()), app)
    menu = QMenu()
    for label, key in (("喂食", "feed"), ("摸摸头", "pet")):
        act = QAction(label, menu)
        if key in actions:
            act.triggered.connect(lambda _=False, k=key: actions[k]())
        else:
            act.setEnabled(False)
        menu.addAction(act)
    menu.addSeparator()
    for label in ("静默模式（M3）", "设置（M5）"):
        act = menu.addAction(label)
        act.setEnabled(False)
    menu.addSeparator()
    quit_act = menu.addAction("退出")
    quit_act.triggered.connect(app.quit)
    tray.setContextMenu(menu)
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
    parser.add_argument("--fast-life", type=float, default=1.0,
                        help="养成时间倍速（调试/验收用，1 = 正常速度）")
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

    # 养成层（T2.1~T2.5）
    save = Save(PROJ_ROOT / "data" / f"pet-{pack.name}.db")
    evolution = Evolution(pack, save)
    print(f"[养成] {evolution.summary()}")

    # display.scale：加载时一次性平滑缩放（此前该字段未生效，2026-10-24 按用户反馈修复）
    pixmaps = {
        name: [
            pm.scaled(
                round(pm.width() * pack.scale), round(pm.height() * pack.scale),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
            )
            for pm in (QPixmap(str(p)) for p in st.frame_paths)
        ]
        for name, st in pack.states.items()
    }

    sm = StateMachine(pack, pixmaps, stats_getter=lambda: evolution.as_dict())
    sm.state_changed.connect(lambda old, new: print(f"[状态] {old} → {new}", flush=True))

    tray_holder: dict = {}

    def refresh_tooltip() -> None:
        tray = tray_holder.get("tray")
        if tray:
            tray.setToolTip(f"{pack.name} · {evolution.stage} · 亲密度 {evolution.intimacy:.0f}")

    def on_interact(iid: str) -> None:
        result = evolution.do(iid)
        if result and result[0]:
            sm.force(result[0], result[1])
        stage = evolution.check_growth()
        if stage:
            print(f"[成长] 🎉 亲密度够了，缘缘进入「{stage}」！", flush=True)
            sm.force(pack.startup_state or pack.default_state, 3.0)
        print(f"[养成] {iid}: {evolution.summary()}", flush=True)
        refresh_tooltip()

    actions = {"feed": lambda: on_interact("feed"), "pet": lambda: on_interact("pet")}

    window = PetWindow(pack, sm, actions)
    window.place_on(app.primaryScreen())
    window.show()
    tray_holder["tray"] = _make_tray(app, actions)
    refresh_tooltip()
    print(f"[缘缘] 「{pack.name}」已上桌：拖拽 / 双击互动 / 右键喂食摸摸头 / 托盘退出", flush=True)

    # 生命周期：每分钟演化一次并存档（T2.2）
    def life_tick() -> None:
        evolution.tick((1 / 60) * args.fast_life)
        evolution.save_stats()
        refresh_tooltip()

    life_timer = QTimer()
    life_timer.timeout.connect(life_tick)
    life_timer.start(60_000 if args.smoke <= 0 else 1_000)  # smoke 模式下每秒演化一次便于验收
    app.aboutToQuit.connect(save.close)

    if args.smoke > 0:
        def finish_smoke() -> None:
            shot_dir = PROJ_ROOT / "docs"
            shot_dir.mkdir(exist_ok=True)
            path = shot_dir / f"演示截图-{pack.name}.png"
            window.grab().save(str(path))
            print(f"[养成] 结束时 {evolution.summary()}")
            print(f"[smoke] {args.smoke}s 运行结束，截图 {path}")
            app.quit()
        QTimer.singleShot(int(args.smoke * 1000), finish_smoke)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
