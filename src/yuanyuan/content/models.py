"""宠物包数据模型 —— 与 docs/宠物包格式规范-v0.md 一一对应"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Trigger:
    type: str
    params: dict = field(default_factory=dict)


@dataclass
class FrameState:
    """一个状态 = 一段可播放的动画"""
    name: str
    frame_paths: list[Path]
    fps: float = 4.0
    loop: bool = True
    speed: float | None = None  # movement.speed（px/s）；None = 原地


@dataclass
class Behavior:
    """一个行为 = 从某些状态、被某类触发器、跳到目标状态"""
    id: str
    from_states: list[str]      # ["*"] 表示任意状态
    to_state: str
    trigger: Trigger
    duration: tuple[float, float] | None = None  # 秒；到期回 default_state
    interruptible: bool = True


@dataclass
class PetPack:
    path: Path
    name: str
    scale: float
    anchor: str
    default_state: str
    startup_state: str | None
    startup_duration: float
    states: dict[str, FrameState]
    behaviors: list[Behavior]
    personality: dict
    warnings: list[str] = field(default_factory=list)  # 非致命问题

    def summary(self) -> str:
        lines = [
            f"宠物包「{self.name}」自 {self.path}",
            f"  状态（{len(self.states)}）：{', '.join(self.states)}",
            f"  行为（{len(self.behaviors)}）：{', '.join(b.id for b in self.behaviors)}",
            f"  帧总数：{sum(len(s.frame_paths) for s in self.states.values())}"
            f" | 默认状态：{self.default_state} | 开机状态：{self.startup_state}",
        ]
        lines += [f"  ⚠ {w}" for w in self.warnings]
        return "\n".join(lines)
