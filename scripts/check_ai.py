"""T4.1 验收：Provider 真实调用（读 data/config.json，不打印任何密钥）

运行：python scripts/check_ai.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from yuanyuan.ai.provider import Provider, load_ai_config  # noqa: E402

PROJ_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    cfg = load_ai_config(PROJ_ROOT / "data" / "config.json")
    if cfg is None:
        print("❌ data/config.json 缺失或没有 api_key——AI 功能将优雅降级（这本身是合法状态）")
        return 1
    provider = Provider(cfg)
    print(f"模型：{provider.model} | base_url 主机校验通过")
    reply, tokens = provider.chat([
        {"role": "system", "content": "你是一只叫缘缘的小狗桌宠，只说两个字以内的狗话。"},
        {"role": "user", "content": "跟主人打个招呼"},
    ])
    print(f"回复：{reply}")
    print(f"tokens：{tokens}")
    if reply and tokens > 0:
        print("✅ Provider 真实调用通过")
        return 0
    print("❌ 回复为空")
    return 1


if __name__ == "__main__":
    sys.exit(main())
