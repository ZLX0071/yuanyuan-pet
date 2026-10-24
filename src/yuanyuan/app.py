"""组装层：宠物包 → 养成层 → 状态机 → 窗口；感知层 + 提醒 + 静默 + AI 对话（T4 MVP）"""

from __future__ import annotations

import argparse
import datetime
import queue
import random
import re
import sys
import threading
import time
from pathlib import Path

import psutil
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from yuanyuan.ai.notes import (NOTE_VIEW_RE, add_note, due_notes, extract_note,
                               mark_reminded, pending_notes)
from yuanyuan.ai.provider import AIError, Provider, load_ai_config
from yuanyuan.content.models import PetPack
from yuanyuan.content.pack_loader import PackError, load_pack
from yuanyuan.engine.animator import StateMachine
from yuanyuan.engine.bubble import Bubble, ChatInput
from yuanyuan.engine.pet_window import PetWindow
from yuanyuan.life.save import Save
from yuanyuan.life.stats import Evolution
from yuanyuan.sense.calendar import CalendarWatch
from yuanyuan.sense.events import SenseAggregator
from yuanyuan.sense.focus import FocusTimer
from yuanyuan.sense.hooks import ForegroundPoller, start_hooks
from yuanyuan.sense.reminders import ReminderScheduler

PROJ_ROOT = Path(__file__).resolve().parents[2]
INTERACTION_MENU = (("喂食", "feed"), ("摸摸头", "pet"), ("玩球", "play_ball"),
                    ("握手", "shake"), ("洗澡", "bath"))


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
    for label, key in INTERACTION_MENU:
        act = QAction(label, menu)
        act.triggered.connect(lambda _=False, k=key: actions[k]())
        menu.addAction(act)
    chat = QAction("跟缘缘说话", menu)
    chat.triggered.connect(lambda: actions["chat"]())
    menu.addAction(chat)
    menu.addSeparator()
    a_focus = QAction("开始专注 (25 分钟)", menu)
    a_focus.triggered.connect(lambda: actions["toggle_focus"]())
    menu.addAction(a_focus)
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
    return tray, {"silent": a_silent, "focus": a_focus}


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
    parser.add_argument("--test-chat", type=str, default=None,
                        help="启动 5 秒后自动发送一句话（验收对话链路用）")
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
    print(f"[养成] {evolution.summary()}（第 {evolution.day_count()} 天 / 连续 {evolution.streak} 天）")

    # AI 层（T4.1）：配置缺失时优雅降级
    ai_cfg = load_ai_config(PROJ_ROOT / "data" / "config.json")
    provider = Provider(ai_cfg) if ai_cfg else None
    if provider:
        print(f"[AI] 已接入 {provider.model}（月度额度 {int(ai_cfg['monthly_token_budget']):,} tokens）")
    else:
        print("[AI] 未配置（data/config.json），对话功能停用，其余一切正常")

    # 素材：原始帧保留一份，体型随成长阶段缩放（M2.5-N4）
    raw_pixmaps = {name: [QPixmap(str(p)) for p in st.frame_paths]
                   for name, st in pack.states.items()}

    def build_scaled(multiplier: float) -> dict:
        return {name: [pm.scaled(round(pm.width() * multiplier), round(pm.height() * multiplier),
                                 Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
                       for pm in pms]
                for name, pms in raw_pixmaps.items()}

    sm = StateMachine(pack, build_scaled(pack.scale * evolution.stage_scale()))
    _t0 = time.monotonic()
    sm.state_changed.connect(
        lambda old, new: print(f"[状态] +{time.monotonic() - _t0:6.1f}s {old} → {new}", flush=True)
    )

    tray_holder: dict = {}
    silent = {"on": False}
    fullscreen = {"on": False}
    focus = FocusTimer()
    sm.focus = focus  # 专注时引擎抑制自动行为（安静陪坐）
    calendar_watch = CalendarWatch(PROJ_ROOT / "data")

    def apply_stage_scale() -> None:
        sm.pixmaps = build_scaled(pack.scale * evolution.stage_scale())
        window.apply_size(max(pm.width() for pms in sm.pixmaps.values() for pm in pms),
                          max(pm.height() for pms in sm.pixmaps.values() for pm in pms))

    # AI 对话（T4.2/T4.3/T4.4/T4.6）：气泡 + 异步线程 + 长度护栏
    bubble = Bubble()
    chat_input = ChatInput()
    chat_q: queue.Queue = queue.Queue()

    def build_system() -> str:
        persona = (pack.personality or {}).get("prompt", "你是一只可爱的桌宠小狗。")
        return (f"{persona}\n当前状态：{evolution.stage}期，饱食 {evolution.hunger:.0f}，"
                f"心情 {evolution.mood:.0f}，亲密度 {evolution.intimacy:.0f}，"
                f"你们已经陪伴 {evolution.day_count()} 天，连续陪伴 {evolution.streak} 天。"
                "用一两句话回复，像狗狗一样说话，可以偶尔提到当前状态。")

    def build_messages(user_text: str) -> list[dict]:
        history = save.get("chat_history", []) or []
        return [{"role": "system", "content": build_system()}] + history[-6:] + \
               [{"role": "user", "content": user_text}]

    def _bump_usage(tokens: int) -> None:
        usage_key = f"ai_usage_{time.strftime('%Y%m')}"
        used = int(save.get(usage_key, 0) or 0)
        save.set(usage_key, used + tokens)
        print(f"[AI] tokens +{tokens}（本月 {used + tokens:,}）", flush=True)

    def _within_budget() -> bool:
        used = int(save.get(f"ai_usage_{time.strftime('%Y%m')}", 0) or 0)
        return ai_cfg is None or used < int(ai_cfg["monthly_token_budget"])

    def _ai_chat(user_text: str) -> str:
        assert provider is not None and ai_cfg is not None
        if not _within_budget():
            return "（这个月的脑力额度用完啦，下个月再聊…）"
        reply, tokens = provider.chat(build_messages(user_text))
        _bump_usage(tokens)
        history = save.get("chat_history", []) or []
        history += [{"role": "user", "content": user_text}, {"role": "assistant", "content": reply}]
        save.set("chat_history", history[-20:])  # 滚动保留最近 10 轮
        return reply

    def send_chat(text: str) -> None:
        sm.note_interaction()
        if NOTE_VIEW_RE.search(text):  # 本地快路径：看记事不打 AI
            notes = pending_notes(save)
            if not notes:
                bubble.show_text("（现在没有待办的记事哦）", 8)
            else:
                lines = [f"• {n['text']}" + (f"（{n['due']} 提醒）" if n.get("due") else "")
                         for n in notes[:8]]
                bubble.show_text("你的记事：\n" + "\n".join(lines), 20)
            return
        if provider is None:
            bubble.show_text("（还没有配置 AI 服务：把 API 信息写进 data/config.json 就能聊啦）", 8)
            return
        bubble.show_text("……", None)
        threading.Thread(target=_chat_worker, args=(text,), daemon=True).start()

    def _chat_worker(text: str) -> None:
        try:
            reply = _ai_chat(text)
            try:
                note = extract_note(provider, text)  # 启发式闸门命中才多花一次小调用
            except AIError:
                note = None
            if note:
                add_note(save, note)
                due_s = f"，{note['due']} 提醒你" if note.get("due") else ""
                reply += f"\n（记下啦：{note['text']}{due_s}）"
            chat_q.put(reply)
        except AIError as e:
            chat_q.put(f"（{e}）")

    def maybe_proactive(ev: str) -> None:
        """T4.5 主动搭话：特定感知事件低频触发，每日上限来自宠物包 personality.proactive"""
        if provider is None or silent["on"] or fullscreen["on"] or focus.on:
            return
        max_n = int((pack.personality or {}).get("proactive", {}).get("max_per_day", 5))
        key = f"proactive_{time.strftime('%Y%m%d')}"
        count = int(save.get(key, 0) or 0)
        if count >= max_n or random.random() > 0.4:  # 非加密用途：主动搭话的概率掷签
            return
        save.set(key, count + 1)
        context = "主人刚回到电脑前" if ev == "user_return" else "主人已经连续工作一个小时了"

        def worker() -> None:
            try:
                msgs = [{"role": "system",
                         "content": build_system() + f"\n现在{context}。主动说一句话（15 字内），不要提问。"}]
                reply, tokens = provider.chat(msgs)
                _bump_usage(tokens)
                chat_q.put(reply)
            except AIError:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def on_interact(iid: str) -> None:
        sm.note_interaction()  # 菜单交互重置闲置/睡觉计时
        result = evolution.do(iid)
        if result and result[0] == "__cooldown__":
            bubble.place_above(window.frameGeometry())
            bubble.show_text("（刚刚才做过啦，休息一下嘛）", 5)
            return
        if result and result[0]:
            sm.force(result[0], result[1])
        stage = evolution.check_growth()
        if stage:
            print(f"[成长] 🎉 亲密度够了，缘缘进入「{stage}」！", flush=True)
            sm.force(pack.startup_state or pack.default_state, 3.0)
            apply_stage_scale()  # 体型跟着长大（N4）
        print(f"[养成] {iid}: {evolution.summary()}", flush=True)
        refresh_tooltip()

    actions: dict = {key: (lambda k=key: on_interact(k)) for key, _ in INTERACTION_MENU}

    def toggle_silent() -> None:
        silent["on"] = not silent["on"]
        (window.hide if silent["on"] else window.show)()
        tray_refs["silent"].setText("取消静默 (Ctrl+Alt+Y)" if silent["on"] else "静默模式 (Ctrl+Alt+Y)")
        refresh_tooltip()
        print(f"[静默] {'开启：宠物隐藏，提醒暂停' if silent['on'] else '关闭'}", flush=True)

    def open_chat() -> None:
        chat_input.place_above(window.frameGeometry())
        chat_input.focus()

    def toggle_focus() -> None:
        if focus.on:
            focus.cancel()
            tray_refs["focus"].setText("开始专注 (25 分钟)")
            bubble.show_text("（专注取消啦，随时再叫我陪你）", 6)
            print("[专注] 已取消", flush=True)
        else:
            mins = int(focus.start(time.monotonic()) // 60)
            sm.force(pack.default_state)
            bubble.place_above(window.frameGeometry())
            bubble.show_text(f"接下来 {mins} 分钟我安静陪你～", 8)
            tray_refs["focus"].setText("结束专注")
            print(f"[专注] 开始 {mins} 分钟（期间缘缘安静陪坐）", flush=True)

    actions["toggle_silent"] = toggle_silent
    actions["chat"] = open_chat
    actions["toggle_focus"] = toggle_focus
    chat_input.send_requested.connect(send_chat)

    window = PetWindow(pack, sm, actions=actions, silent=silent, focus=focus)
    window.place_on(app.primaryScreen())
    window.show()

    reminders = ReminderScheduler(pack.sense_cfg, t0=time.monotonic())
    tray, tray_refs = _make_tray(app, actions, reminders)
    tray_holder["tray"] = tray

    def refresh_tooltip() -> None:
        tip = (f"{pack.name} · {evolution.stage} · 第 {evolution.day_count()} 天 / 连续 {evolution.streak} 天\n"
               f"饱食 {evolution.hunger:.0f} · 心情 {evolution.mood:.0f} · 亲密度 {evolution.intimacy:.0f}")
        if silent.get("on"):
            tip += "\n静默中"
        if provider:
            tip += f"\nAI：{provider.model}"
        tray.setToolTip(tip)

    refresh_tooltip()
    print(f"[缘缘] 「{pack.name}」已上桌：拖拽 / 双击互动 / 右键菜单 / Ctrl+Alt+Y 静默", flush=True)

    # 感知层（T3）
    raw_q: queue.Queue = queue.Queue()
    try:
        hooks = start_hooks(raw_q)
        print("[感知] 键盘/鼠标/全局热键监听已启动（Ctrl+Alt+Y 静默）", flush=True)
    except Exception as e:
        hooks = None
        print(f"⚠ 键鼠监听启动失败（{e}），提醒与静默热键不可用", flush=True)
    aggregator = SenseAggregator(t0=time.monotonic())
    poller = ForegroundPoller()
    last_reply = {"text": None}

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
        try:
            while True:
                reply = chat_q.get_nowait()
                print(f"[AI] 缘缘：{reply[:60]}", flush=True)
                last_reply["text"] = reply
                bubble.place_above(window.frameGeometry())
                bubble.show_text(reply, 15)
        except queue.Empty:
            pass
        hwnd, changed = poller.poll()
        fullscreen["on"] = poller.is_fullscreen(hwnd)
        if changed:
            aggregator.set_foreground_changed(now)
        for ev in aggregator.poll(now):
            print(f"[感知] {ev}", flush=True)
            sm.on_sense(ev)
            if ev in ("user_return", "work_marathon"):
                maybe_proactive(ev)
        for kind, message in reminders.due(now):
            if silent["on"] or fullscreen["on"]:
                continue  # 延后：不 mark_fired，下个周期继续到期
            tray.showMessage("缘缘提醒", message, QSystemTrayIcon.MessageIcon.Information, 6000)
            reminders.mark_fired(kind, now)
            sm.force(pack.startup_state or pack.default_state, 2.5)
            print(f"[提醒] {kind}: {message}", flush=True)
        if focus.poll(now):  # 番茄钟完成（M4.5-F-D）
            count_key = f"pomodoro_{time.strftime('%Y%m%d')}"
            count = int(save.get(count_key, 0) or 0) + 1
            save.set(count_key, count)
            result = evolution.do("focus_done")
            if result and result[0]:
                sm.force(result[0], result[1])
            tray.showMessage("专注完成！", f"第 {count} 个番茄钟达成，缘缘很开心！", QSystemTrayIcon.MessageIcon.Information, 6000)
            print(f"[专注] 完成，今天第 {count} 个", flush=True)
            refresh_tooltip()
        for summary, start in calendar_watch.scan(datetime.datetime.now()):  # 日历（F-C）
            msg = f"{summary}（{start:%H:%M} 开始）"
            tray.showMessage("日程提醒", msg, QSystemTrayIcon.MessageIcon.Information, 6000)
            bubble.place_above(window.frameGeometry())
            bubble.show_text(f"（快到日程啦：{summary}！）", 10)
            sm.force(pack.startup_state or pack.default_state, 2.5)
            print(f"[日程] {msg}", flush=True)
        for n in due_notes(save, datetime.datetime.now()):  # 记事到期（F-B）
            mark_reminded(save, n["id"])
            msg = f"别忘了：{n['text']}"
            tray.showMessage("缘缘提醒", msg, QSystemTrayIcon.MessageIcon.Information, 6000)
            bubble.place_above(window.frameGeometry())
            bubble.show_text(f"（{msg}！）", 10)
            sm.force(pack.startup_state or pack.default_state, 2.5)
            print(f"[记事] {msg}", flush=True)

    life_timer = QTimer()
    life_timer.timeout.connect(lambda: (evolution.tick((1 / 60) * args.fast_life),
                                        evolution.save_stats(), refresh_tooltip()))
    life_timer.start(60_000 if args.smoke <= 0 else 1_000)

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

    if args.test_chat:
        QTimer.singleShot(5000, lambda: send_chat(args.test_chat))

    if args.smoke > 0:
        def finish_smoke() -> None:
            shot_dir = PROJ_ROOT / "docs"
            shot_dir.mkdir(exist_ok=True)
            if last_reply["text"]:  # 截图前把最后一条回复钉在气泡上，便于视觉验收
                bubble.place_above(window.frameGeometry())
                bubble.show_text(last_reply["text"], None)
                bubble.grab().save(str(shot_dir / f"演示截图-气泡-{pack.name}.png"))
            path = shot_dir / f"演示截图-{pack.name}.png"
            window.grab().save(str(path))
            proc = psutil.Process()
            cpu = proc.cpu_percent(interval=1.5)
            mem = proc.memory_info().rss / 1024 / 1024
            print(f"[性能] 全功能空闲：CPU 单核 {cpu:.1f}% | 内存 {mem:.0f} MB")
            print(f"[养成] 结束时 {evolution.summary()}")
            print(f"[smoke] {args.smoke}s 运行结束，截图 {path}")
            app.quit()
        QTimer.singleShot(int(args.smoke * 1000), finish_smoke)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
