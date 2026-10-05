"""MaaFramework agent 的自訂動作註冊：MFAAvalonia 執行任務時呼叫。"""
from __future__ import annotations

from maa.agent.agent_server import AgentServer

from abyss_runner import ReadAbyssAction
from key_setup import SetKeyAction
from members_runner import ReadMembersAction, ReadMissingMembersAction
from upload_runner import UploadAction

AgentServer.custom_action("SetKey")(SetKeyAction)
AgentServer.custom_action("ReadMembers")(ReadMembersAction)
# 任務選項「捨棄本機結果重新讀取」為「是」時，ReadMembers 節點改用這個動作
AgentServer.register_custom_action("ReadMembersDiscard", ReadMembersAction(discard=True))
AgentServer.custom_action("ReadMissingMembers")(ReadMissingMembersAction)
AgentServer.custom_action("ReadAbyss")(ReadAbyssAction)
AgentServer.custom_action("Upload")(UploadAction)
