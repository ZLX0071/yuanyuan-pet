"""全局配置读写（data/config.json）：按节合并，避免互相覆盖。

结构：{"ai": {...}, "ui": {"last_pack": ...}, "dnd": {"enabled", "start", "end"}}
"""

from __future__ import annotations

import json
from pathlib import Path


def load_config(path: str | Path) -> dict:
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_section(path: str | Path, section: str, value) -> None:
    """只更新一个节，保留其余节（如 ai 不被 ui 写入清掉）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_config(path)
    data[section] = value
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
