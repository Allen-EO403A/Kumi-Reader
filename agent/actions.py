"""MaaFramework agent 的自訂動作註冊：MFAAvalonia 執行任務時呼叫。"""
from __future__ import annotations

from maa.agent.agent_server import AgentServer

from abyss_runner import ReadAbyssAction
from key_setup import SetKeyAction
from members_runner import ReadMembersAction, ReadMembersPageAction

AgentServer.custom_action("SetKey")(SetKeyAction)
AgentServer.custom_action("ReadMembers")(ReadMembersAction)
AgentServer.custom_action("ReadMembersPage")(ReadMembersPageAction)
AgentServer.custom_action("ReadAbyss")(ReadAbyssAction)
