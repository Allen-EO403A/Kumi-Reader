"""MaaFramework 自訂動作：MFAAvalonia 執行任務時呼叫。"""
from __future__ import annotations

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from kumi_reader import log
from kumi_reader.session import start_session


@AgentServer.custom_action("ReadMembers")
class ReadMembers(CustomAction):
    """讀取家族成員並上傳。"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        session = start_session("members")
        if session is None:
            return False
        # 讀取流程在 R2 實作
        log.warn("讀取流程尚未實作。")
        return True
