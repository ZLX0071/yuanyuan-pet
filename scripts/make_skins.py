"""官方皮肤包生成：复制缘缘包 → 替换指定状态的图 → 改名成新皮肤包。

运行：python scripts/make_skins.py
产物：pets/yuanyuan-newyear（新春唐装版）、pets/yuanyuan-princess（公主蝴蝶结版）
"""

import json
import shutil
import sys
from pathlib import Path

from PIL import Image
from rembg import new_session, remove

PROJ_ROOT = Path(__file__).resolve().parents[1]
ASSETS = PROJ_ROOT / "assets" / "缘缘-参考图"
BASE = PROJ_ROOT / "pets" / "yuanyuan"
SESSION = new_session("u2net")
TARGET_H = 384
MAX_W = 512

# (皮肤目录, 显示名, 描述, {状态: 参考图})
SKINS = [
    ("yuanyuan-newyear", "缘缘·新春版", "红唐装过年皮肤：换上拜年服的缘缘",
     {"idle": "04-红色唐装-新春皮肤.jpg", "excited": "15-红色运动衫-跳跃奔跑.jpg"}),
    ("yuanyuan-princess", "缘缘·公主版", "蝴蝶结项链公主皮肤：盛装打扮的缘缘",
     {"idle": "11-蝴蝶结项链-公主皮肤.jpg", "eat": "03-泡泡浴-彩蛋.jpg"}),
]


def cutout(src: Path) -> Image.Image:
    img = remove(Image.open(src).convert("RGB"), session=SESSION)
    img = img.crop(img.getbbox())
    w, h = img.size
    scale = TARGET_H / h if TARGET_H / h * w <= MAX_W else MAX_W / w
    if scale < 1.0:
        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
        img = img.resize((round(w * scale), round(h * scale)), resample)
    return img


def main() -> int:
    for folder, name, desc, swaps in SKINS:
        target = PROJ_ROOT / "pets" / folder
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(BASE, target)
        for state, src_name in swaps.items():
            out = target / "sprites" / state / f"{state}_0.png"
            cutout(ASSETS / src_name).save(str(out))
            print(f"[皮肤] {name}: {state} ← {src_name}")
        manifest_path = target / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["meta"]["name"] = name
        manifest["meta"]["description"] = desc
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        print(f"✅ 皮肤包已生成：{target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
