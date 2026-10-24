"""对话式记事（M4.5-F-B）：聊天里说"周三交 PRD"→ LLM 抽取结构化事项 → 本地存储 → 到期提醒。

隐私：记事只存本地 SQLite。抽取是额外一次 LLM 调用，先过启发式闸门（含"记/提醒"等词才触发）。
"""

from __future__ import annotations

import datetime
import json
import re
import uuid

from .provider import Provider, AIError

NOTE_HINTS = re.compile(r"记|提醒|别忘了|记得|要交|开会|交稿|买|预约|deadline|ddl", re.I)
NOTE_VIEW_RE = re.compile(r"看(一?下)?记事|我的记事|记事列表|有什么记事")

_EXTRACT_SYS = (
    "从用户消息中提取待办事项。今天是 {today}（{weekday}）。"
    '只输出一个 JSON 对象：{{"is_note": true/false, "text": "事项简述(20字内)", '
    '"due": "YYYY-MM-DD HH:MM 或 null"}}。'
    "相对时间（周三/明天下午三点）按今天推算成具体日期时间；没有明确时间就是 null；"
    "如果用户不是在记事或要提醒，is_note 为 false。不要输出 JSON 以外的任何内容。"
)


def looks_like_note(text: str) -> bool:
    return bool(NOTE_HINTS.search(text)) and len(text) <= 120


def extract_note(provider: Provider, user_text: str) -> dict | None:
    """抽取记事；不是记事/解析失败返回 None（fail-open，不影响正常聊天）。"""
    if not looks_like_note(user_text):
        return None
    today = datetime.date.today()
    weekday = "周" + "一二三四五六日"[today.weekday()]
    reply, _ = provider.chat([
        {"role": "system", "content": _EXTRACT_SYS.format(today=today.isoformat(), weekday=weekday)},
        {"role": "user", "content": user_text},
    ])
    match = re.search(r"\{.*\}", reply, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not data.get("is_note"):
        return None
    note = {
        "id": uuid.uuid4().hex[:8],
        "text": str(data.get("text", user_text))[:80],
        "due": data.get("due"),
        "created": datetime.datetime.now().isoformat(timespec="minutes"),
        "reminded": False,
    }
    if note["due"]:
        try:
            datetime.datetime.fromisoformat(str(note["due"]))
        except ValueError:
            note["due"] = None
    return note


# ---- 存储（Save KV；全部本地）----

def add_note(save, note: dict) -> None:
    notes = save.get("notes", []) or []
    notes.append(note)
    save.set("notes", notes)


def pending_notes(save) -> list[dict]:
    return [n for n in (save.get("notes", []) or []) if not n.get("reminded")]


def due_notes(save, now: datetime.datetime) -> list[dict]:
    out = []
    for n in pending_notes(save):
        if not n.get("due"):
            continue
        try:
            if datetime.datetime.fromisoformat(str(n["due"])) <= now:
                out.append(n)
        except ValueError:
            continue
    return out


def mark_reminded(save, note_id: str) -> None:
    notes = save.get("notes", []) or []
    for n in notes:
        if n.get("id") == note_id:
            n["reminded"] = True
    save.set("notes", notes)


def delete_note(save, note_id: str) -> None:
    """完成/删除：直接从列表移除。"""
    notes = [n for n in (save.get("notes", []) or []) if n.get("id") != note_id]
    save.set("notes", notes)
