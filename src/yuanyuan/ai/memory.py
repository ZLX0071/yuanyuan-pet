"""长期记忆（P1-1）：对话历史溢出时 LLM 摘要成"她记得的事实"，注入人格。

策略：chat_history 超过阈值（20 条）→ 把最旧一段（10 条）摘要为 ≤5 条事实
→ 存 memory_facts（上限 30 条，FIFO）→ 系统提示词注入最近 8 条。
摘要失败（无 AI/网络错）静默跳过，滚动窗口照常截断（不阻塞聊天）。
"""

from __future__ import annotations

HISTORY_THRESHOLD = 20   # 超过即触发摘要
SEGMENT = 10             # 每次摘要的条数
MAX_FACTS = 30
INJECT_TOP = 8

_SUMMARY_SYS = (
    "把下面这段主人和桌宠缘缘的对话，提炼成不超过 5 条'值得记住的事实'（每条 25 字内）。"
    "只记关于主人的稳定信息：喜好/习惯/重要的事/养了什么/重要日期。"
    "输出 JSON 数组，如 [\"主人喜欢喝美式\", ...]。没有值得记的就输出 []。"
)


def summarize_segment(provider, segment: list[dict]) -> list[str]:
    """把一段对话摘要为事实列表；任何失败返回 []（fail-open）。"""
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in segment)
    try:
        reply, _ = provider.chat([
            {"role": "system", "content": _SUMMARY_SYS},
            {"role": "user", "content": convo[:4000]},
        ])
    except Exception:
        return []
    import json
    import re
    m = re.search(r"\[.*\]", reply, re.S)
    if not m:
        return []
    try:
        facts = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return [str(f)[:60] for f in facts if isinstance(f, (str, int, float)) and str(f).strip()][:5]


def maintain(save, provider) -> list[str]:
    """聊天后调用：必要时摘要溢出段。返回本次新增的事实（可为空）。"""
    history = save.get("chat_history", []) or []
    if len(history) < HISTORY_THRESHOLD or provider is None:
        return []
    segment, kept = history[:SEGMENT], history[SEGMENT:]
    new_facts = summarize_segment(provider, segment)
    save.set("chat_history", kept)
    if new_facts:
        facts = (save.get("memory_facts", []) or []) + new_facts
        save.set("memory_facts", facts[-MAX_FACTS:])
        print(f"[记忆] 记住了 {len(new_facts)} 件事：{new_facts}", flush=True)
    return new_facts


def inject_block(save) -> str:
    """系统提示词注入块：'她记得的事'。"""
    facts = (save.get("memory_facts", []) or [])[-INJECT_TOP:]
    if not facts:
        return ""
    lines = "\n".join(f"- {f}" for f in facts)
    return f"\n你长期记得关于主人的这些事（自然地用，别一次全背出来）：\n{lines}"
