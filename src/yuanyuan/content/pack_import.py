"""宠物包导入（T6.3）：zip → 安全解压 → 校验 → 安装到 pets/ 目录。

安全边界（zip slip 防护）：
- 拒绝绝对路径与含 ".." 的条目；
- manifest 必须在 zip 内的某个子文件夹里（要求"选中文件夹压缩"的标准打包方式）；
- 校验失败自动回滚（删除已解压内容）。
"""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

from .pack_loader import load_pack


class ImportError_(Exception):
    """导入失败，消息直接展示给用户。"""


def import_pack_zip(zip_path: str | Path, pets_dir: Path) -> tuple[str, list[str]]:
    """导入一个宠物包 zip。返回 (包显示名, warnings)。失败抛 ImportError_（人话）。"""
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise ImportError_("找不到要导入的 zip 文件")
    pets_dir.mkdir(parents=True, exist_ok=True)

    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as e:
        raise ImportError_("这不是一个合法的 zip 文件") from e

    with zf:
        names = zf.namelist()
        for n in names:
            p = Path(n)
            if p.is_absolute() or ".." in p.parts:
                raise ImportError_(f"zip 内含不安全路径（{n}），已拒绝导入")
        # 双保险：解压目标逐条规范化，必须落在 pets/ 目录内（防不同盘符等边角）
        pets_root = str(pets_dir.resolve())
        for n in names:
            resolved = str((pets_dir / n).resolve())
            try:
                if os.path.commonpath([pets_root, resolved]) != pets_root:
                    raise ImportError_(f"zip 条目越界（{n}），已拒绝导入")
            except ValueError as e:  # 不同盘符等
                raise ImportError_(f"zip 条目越界（{n}），已拒绝导入") from e
        manifests = [n for n in names if Path(n).name == "manifest.json"]
        if not manifests:
            raise ImportError_(
                "zip 里没找到 manifest.json——请确认打包的是完整宠物包"
                "（选中宠物包文件夹后压缩，保证 zip 里有一个文件夹）")
        # 选最浅的 manifest 作为包根
        top = min(manifests, key=lambda n: n.count("/"))
        root_dir = top.split("/")[0]
        if root_dir in ("", ".", ".."):
            raise ImportError_("zip 结构不符合规范：manifest.json 应位于包文件夹内"
                               "（选中文件夹压缩，而不是选中里面的文件）")
        target = pets_dir / root_dir
        if target.exists():
            raise ImportError_(f"pets/ 里已经有「{root_dir}」了——请先删掉旧的，"
                               "或把 zip 里的文件夹改个名字再导入")
        zf.extractall(pets_dir)

    try:
        pack = load_pack(target)
    except Exception:
        shutil.rmtree(target, ignore_errors=True)  # 校验失败回滚
        raise
    return pack.name, pack.warnings
