#!/usr/bin/env python3
"""启动 CLI 命令行排班助手"""
import sys
from pathlib import Path

_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "agent"))

from agent.main import main

if __name__ == "__main__":
    main()
