"""缘缘桌宠启动入口：python main.py [--pack pets/xxx] [--smoke N]"""

import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from yuanyuan.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
