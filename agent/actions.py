# Kumi Reader - 讀取「忍者必須死3」家族成員與深淵排行並上傳到 Kumi
# Copyright (C) 2026 Allen <allen@umail.tw>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
