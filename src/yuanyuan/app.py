"""组装层：宠物包 → 养成层 → 状态机 → 窗口；感知层（键鼠→聚合→sense 行为）+ 提醒 + 静默"""

from __future__ import annotations

import argparse
import queue
import sys
import time
from pathlib import Path

import psutil
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from yuanyuan.content.models import PetPack
from yuanyuan.content.pack_loader import PackError, load_pack
from yuanyuan.engine.animator import StateMachine
from yuanyuan.engine.pet_window import PetWindow
from yuanyuan.life.save import Save
from yuanyuan.life.stats import Evolution
from yuanyuan.sense.events import SenseAggregator
from yuanyuan.sense.hooks import ForegroundPoller, start_hooks
from yuanyuan.sense.reminders import ReminderScheduler

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


def _make_tray(app: QApplication, actions: dict, reminders: ReminderScheduler
               ) -> tuple[QSystemTrayIcon, dict]:
    tray = QSystemTrayIcon(QIcon(_tray_icon_pixmap()), app)
    menu = QMenu()
    for label, key in (("喂食", "feed"), ("摸摸头", "pet")):
        act = QAction(label, menu)
        act.triggered.connect(lambda _=False, k=key: actions[k]())
        menu.addAction(act)
    menu.addSeparator()
    a_silent = QAction("静默模式 (Ctrl+Alt+Y)", menu)
    a_silent.triggered.connect(lambda: actions["toggle_silent"]())
    menu.addAction(a_silent)
    menu_rem = menu.addMenu("提醒")
    for kind, label in (("water", "喝水提醒"), ("rest", "久坐提醒")):
        ra = QAction(label, menu_rem)
        ra.setCheckable(True)
        ra.setChecked(reminders.is_enabled(kind))
        ra.toggled.connect(lambda on, k=kind: reminders.set_enabled(k, on))
        menu_rem.addAction(ra)
    menu.addSeparator()
    quit_act = menu.addAction("退出")
    quit_act.triggered.connect(app.quit)
    tray.setContextMenu(menu)
    tray.show()
    return tray, {"silent": a_silent}


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

    # 养成层
    save = Save(PROJ_ROOT / "data" / f"pet-{pack.name}.db")
    evolution = Evolution(pack, save)
    print(f"[养成] {evolution.summary()}")

    # display.scale：加载时一次性平滑缩放
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
    _t0 = time.monotonic()
    sm.state_changed.connect(
        lambda old, new: print(f"[状态] +{time.monotonic() - _t0:6.1f}s {old} → {new}", flush=True)
    )

    tray_holder: dict = {}

    def refresh_tooltip() -> None:
        tray = tray_holder.get("tray")
        if tray:
            tip = f"{pack.name} · {evolution.stage} · 亲密度 {evolution.intimacy:.0f}"
            if silent.get("on"):
                tip += " · 静默中"
            tray.setToolTip(tip)

    def on_interact(iid: str) -> None:
        sm.note_interaction()  # 菜单交互也算互动：重置闲置/睡觉计时
        result = evolution.do(iid)
        if result and result[0]:
            sm.force(result[0], result[1])
        stage = evolution.check_growth()
        if stage:
            print(f"[成长] 🎉 亲密度够了，缘缘进入「{stage}」！", flush=True)
            sm.force(pack.startup_state or pack.default_state, 3.0)
        print(f"[养成] {iid}: {evolution.summary()}", flush=True)
        refresh_tooltip()

    # 感知层（T3.2~T3.5）
    silent = {"on": False}
    raw_q: queue.Queue = queue.Queue()
    try:
        hooks = start_hooks(raw_q)
        print("[感知] 键盘/鼠标/全局热键监听已启动（Ctrl+Alt+Y 静默）", flush=True)
    except Exception as e:  # 兜底：监听失败不拦住整个应用
        hooks = None
        print(f"⚠ 键鼠监听启动失败（{e}），提醒与静默热键不可用", flush=True)
    aggregator = SenseAggregator(t0=time.monotonic())
    poller = ForegroundPoller()
    reminders = ReminderScheduler(pack.sense_cfg, t0=time.monotonic())

    actions: dict = {"feed": lambda: on_interact("feed"), "pet": lambda: on_interact("pet")}

    window = PetWindow(pack, sm, actions, silent)
    window.place_on(app.primaryScreen())
    window.show()

    def toggle_silent() -> None:
        silent["on"] = not silent["on"]
        (window.hide if silent["on"] else window.show)()
        tray_refs["silent"].setText("取消静默 (Ctrl+Alt+Y)" if silent["on"] else "静默模式 (Ctrl+Alt+Y)")
        refresh_tooltip()
        print(f"[静默] {'开启：宠物隐藏，提醒暂停' if silent['on'] else '关闭'}", flush=True)

    actions["toggle_silent"] = toggle_silent
    tray, tray_refs = _make_tray(app, actions, reminders)
    tray_holder["tray"] = tray
    refresh_tooltip()
    print(f"[缘缘] 「{pack.name}」已上桌：拖拽 / 双击互动 / 右键菜单 / Ctrl+Alt+Y 静默", flush=True)

    # 养成：每分钟演化 + 存档
    def life_tick() -> None:
        evolution.tick((1 / 60) * args.fast_life)
        evolution.save_stats()
        refresh_tooltip()

    life_timer = QTimer()
    life_timer.timeout.connect(life_tick)
    life_timer.start(60_000 if args.smoke <= 0 else 1_000)

    # 感知：4Hz 汇聚原始事件 → 高层事件 → sense 行为 / 提醒
    fullscreen = {"on": False}

    def sense_tick() -> None:
        now = time.monotonic()
        if hooks is not None:
            moved = hooks["state"]["last_move"]
            if moved > aggregator.last_move_seen:
                aggregator.last_move_seen = moved
                aggregator.feed("move", moved)
            try:
                while True:
                    kind, t = raw_q.get_nowait()
                    if kind == "hotkey_silent":
                        toggle_silent()
                        continue
                    aggregator.feed(kind, t)
            except queue.Empty:
                pass
        hwnd, changed = poller.poll()
        fullscreen["on"] = poller.is_fullscreen(hwnd)
        if changed:
            aggregator.set_foreground_changed(now)
        for ev in aggregator.poll(now):
            print(f"[感知] {ev}", flush=True)
            sm.on_sense(ev)
        for kind, message in reminders.due(now):
            if silent["on"] or fullscreen["on"]:
                continue  # 延后：不 mark_fired，下个周期继续到期
            tray.showMessage("缘缘提醒", message, QSystemTrayIcon.MessageIcon.Information, 6000)
            reminders.mark_fired(kind, now)
            sm.force(pack.startup_state or pack.default_state, 2.5)
            print(f"[提醒] {kind}: {message}", flush=True)

    sense_timer = QTimer()
    sense_timer.timeout.connect(sense_tick)
    sense_timer.start(250)

    def stop_everything() -> None:
        save.close()
        if hooks is not None:
            for k in ("keyboard", "mouse", "hotkeys"):
                try:
                    hooks[k].stop()
                except Exception:
                    pass

    app.aboutToQuit.connect(stop_everything)

    if args.smoke > 0:
        def finish_smoke() -> None:
            shot_dir = PROJ_ROOT / "docs"
            shot_dir.mkdir(exist_ok=True)
            path = shot_dir / f"演示截图-{pack.name}.png"
            window.grab().save(str(path))
            proc = psutil.Process()
            cpu = proc.cpu_percent(interval=1.5)
            mem = proc.memory_info().rss / 1024 / 1024
            print(f"[性能] 含感知监听空闲：CPU 单核 {cpu:.1f}% | 内存 {mem:.0f} MB")
            print(f"[养成] 结束时 {evolution.summary()}")
            print(f"[smoke] {args.smoke}s 运行结束，截图 {path}")
            app.quit()
        QTimer.singleShot(int(args.smoke * 1000), finish_smoke)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
