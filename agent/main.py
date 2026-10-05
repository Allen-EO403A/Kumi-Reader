"""MaaFramework agent 入口：由 MFAAvalonia 以 `python agent/main.py <socket_id>` 啟動。"""
import os
import sys

# 中文輸出不亂碼
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)  # type: ignore[attr-defined]
except AttributeError:
    pass

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

from maa.agent.agent_server import AgentServer  # noqa: E402
from maa.toolkit import Toolkit  # noqa: E402

import actions  # noqa: E402,F401  註冊自訂動作


def main() -> None:
    if len(sys.argv) < 2:
        print("用法：python agent/main.py <socket_id>（由 MFAAvalonia 啟動）")
        sys.exit(1)
    Toolkit.init_option(os.path.dirname(AGENT_DIR))
    AgentServer.start_up(sys.argv[-1])
    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()
