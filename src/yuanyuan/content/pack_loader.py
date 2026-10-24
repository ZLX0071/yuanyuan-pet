"""宠物包加载与校验（T1.4）—— 所有错误必须是人话（DoD）"""

from __future__ import annotations

import glob as globmod
import json
import struct
from pathlib import Path

from .models import Behavior, FrameState, PetPack, Trigger

MAX_FRAME_PX = 512
MAX_FRAMES_PER_STATE = 60


class PackError(Exception):
    """宠物包有问题，拒载。消息直接展示给用户。"""


def _png_size(path: Path) -> tuple[int, int] | None:
    """读 PNG 头拿宽高（不引入 GUI 依赖）。非 PNG 返回 None。"""
    try:
        with open(path, "rb") as f:
            head = f.read(24)
    except OSError:
        return None
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def load_pack(pack_dir: str | Path) -> PetPack:
    pack_dir = Path(pack_dir)
    if not pack_dir.is_dir():
        raise PackError(f"找不到宠物包目录：{pack_dir}")

    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.is_file():
        raise PackError(f"宠物包「{pack_dir.name}」缺少 manifest.json —— 每个宠物包必须有这个描述文件")
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PackError(f"「{pack_dir.name}」的 manifest.json 不是合法 JSON（第 {e.lineno} 行附近）：{e.msg}") from e
    if not isinstance(raw, dict):
        raise PackError("manifest.json 的内容应该是一个 {…} 对象")

    meta = raw.get("meta") or {}
    warnings: list[str] = []
    if not meta.get("name"):
        raise PackError("manifest.json 里缺少 meta.name —— 宠物总得有个名字")
    if not meta.get("license"):
        warnings.append("meta.license 缺失：无法确认素材版权来源（v1 起将拒载）")

    # ---- states ----
    states_raw = raw.get("states")
    if not isinstance(states_raw, dict) or not states_raw:
        raise PackError("manifest.json 里没有 states —— 至少要定义一个状态（比如 idle）")

    states: dict[str, FrameState] = {}
    for name, st in states_raw.items():
        if not isinstance(st, dict):
            raise PackError(f"状态 '{name}' 的定义应该是一个 {{…}} 对象")
        frames_spec = st.get("frames")
        paths = sorted(Path(p) for p in globmod.glob(str(pack_dir / frames_spec))) if frames_spec else []
        if not paths:
            raise PackError(f"状态 '{name}' 找不到任何帧图片（按通配符 {frames_spec or '（frames 未填写）'} 查找）—— 请确认 sprites 目录下的文件名")
        for p in paths:
            size = _png_size(p)
            if size is None:
                warnings.append(f"状态 '{name}' 的 {p.name} 不是 PNG，可能没有透明背景")
            elif max(size) > MAX_FRAME_PX:
                warnings.append(f"状态 '{name}' 的 {p.name} 尺寸 {size[0]}x{size[1]} 超过预算 {MAX_FRAME_PX}px")
        if len(paths) > MAX_FRAMES_PER_STATE:
            warnings.append(f"状态 '{name}' 有 {len(paths)} 帧，超过预算 {MAX_FRAMES_PER_STATE} 帧")
        speed = (st.get("movement") or {}).get("speed")
        states[name] = FrameState(
            name=name, frame_paths=paths,
            fps=float(st.get("fps", 4)), loop=bool(st.get("loop", True)),
            speed=float(speed) if speed else None,
        )

    # ---- behaviors ----
    behaviors: list[Behavior] = []
    for b in raw.get("behaviors", []):
        if not isinstance(b, dict):
            raise PackError(f"behaviors 里的每一项都应是 {{…}} 对象，遇到了：{b!r}")
        bid = b.get("id") or f"behavior#{len(behaviors) + 1}"
        to_state = b.get("to")
        if to_state not in states:
            raise PackError(f"行为 '{bid}' 跳转到未定义的状态 '{to_state}' —— 请先在 states 里定义它")
        trig = b.get("trigger") or {}
        if not trig.get("type"):
            raise PackError(f"行为 '{bid}' 缺少 trigger.type（触发器类型）")
        frm = b.get("from", "*")
        if frm == "*":
            from_states = ["*"]
        elif isinstance(frm, str):
            from_states = [frm]
        else:
            from_states = list(frm)
        unknown = [s for s in from_states if s != "*" and s not in states]
        if unknown:
            raise PackError(f"行为 '{bid}' 的 from 引用了未定义的状态：{', '.join(unknown)}")
        duration = b.get("duration_s")
        behaviors.append(Behavior(
            id=bid, from_states=from_states, to_state=to_state,
            trigger=Trigger(type=trig["type"], params={k: v for k, v in trig.items() if k != "type"}),
            duration=tuple(map(float, duration)) if duration else None,
            interruptible=bool(b.get("interruptible", True)),
        ))

    # ---- 顶层字段 ----
    default_state = raw.get("default_state", "idle")
    if default_state not in states:
        warnings.append(f"default_state '{default_state}' 未定义，改用第一个状态 '{next(iter(states))}'")
        default_state = next(iter(states))
    startup_state = raw.get("startup_state")
    if startup_state is not None and startup_state not in states:
        warnings.append(f"startup_state '{startup_state}' 未定义，忽略")
        startup_state = None

    return PetPack(
        path=pack_dir, name=str(meta["name"]),
        scale=float((raw.get("display") or {}).get("scale", 1.0)),
        anchor=(raw.get("display") or {}).get("anchor", "bottom_center"),
        default_state=default_state,
        startup_state=startup_state,
        startup_duration=float(raw.get("startup_duration_s", 2.5)),
        states=states, behaviors=behaviors,
        personality=raw.get("personality") or {},
        warnings=warnings,
    )
