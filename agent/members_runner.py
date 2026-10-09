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

"""「讀取家族成員」與「補讀缺少的成員」：只讀取並存在本機，由「上傳讀取結果」任務上傳。

不 import AgentServer：MFAAvalonia 的 agent（actions.py）與開發工具（tools/dev_run.py）都呼叫這裡。
載入 AgentServer 後 MaaFramework 會進入 agent 模式，開發工具就不能自己連模擬器。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from maa.context import Context
from maa.custom_action import CustomAction

import local_results as store
from kumi_reader import log
from kumi_reader.device import Device, MaaDevice
from kumi_reader.session import project_root
from members_flow import MembersReader, MembersResult


def save_debug_image(data_dir: Path, image: np.ndarray | None) -> None:
    """停止時的畫面存到 data/debug/，方便查原因（含其他玩家資料，不上傳、不提交）。"""
    if image is None:
        return
    from PIL import Image

    folder = data_dir / "debug"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"stop-{time.strftime('%Y%m%d-%H%M%S')}.png"
    Image.fromarray(image[:, :, ::-1]).save(path)
    log.info(f"停止時的畫面已存到 {path}")


def parse_expected(argv: CustomAction.RunArg) -> int | None:
    """MFAAvalonia 任務選項「家族成員數」：空白表示用畫面上的數字。"""
    try:
        value = str(json.loads(argv.custom_action_param or "{}").get("expectedCount", "")).strip()
    except (ValueError, AttributeError):
        return None
    return int(value) if value.isdigit() and int(value) > 0 else None


def read_members(device: Device, data_dir: Path, expected: int | None, resume: bool, discard: bool = False) -> bool:
    """resume=False：重新讀取（本機有還沒上傳的結果時停下，除非 discard）。
    resume=True：補讀，接續本機進度，從最上面滑到底只讀還沒讀過的列。"""
    progress = store.load_members(data_dir)
    if resume:
        if progress is None or not progress["members"]:
            log.error("本機沒有可以補讀的進度。請先執行「讀取家族成員」。")
            return False
        if progress["complete"]:
            log.warn("上次已經讀完，不需要補讀。" + ("請執行「上傳讀取結果」。" if progress["pending"] else ""))
            return True
        log.info(f"接續本機進度：已讀 {len(progress['members'])} 人，這次只讀還沒讀過的。")
    else:
        if progress is not None and progress["pending"] and progress["members"] and not discard:
            log.error(
                f"本機還有 {len(progress['members'])} 人的讀取結果沒有上傳。"
                "請先執行「上傳讀取結果」或「補讀缺少的成員」；確定不要這份結果時，"
                "在任務選項把「捨棄本機結果重新讀取」設為「是」。"
            )
            return False
        if progress is not None and progress["members"]:
            log.warn(f"捨棄本機先前的進度（{len(progress['members'])} 人），重新讀取。")
        progress = store.new_members_progress()
    log.info("開始補讀缺少的成員…" if resume else "開始讀取家族成員…")

    def on_progress(result: MembersResult, done: set) -> None:
        progress["members"] = result.members
        progress["doneKeys"] = [list(k) for k in done]
        progress["expected"] = result.expected
        progress["pending"] = True
        store.save_members(data_dir, progress)

    before = len(progress["members"])
    reader = MembersReader(
        device,
        done_keys={tuple(k) for k in progress["doneKeys"]},
        known=progress["members"],
        on_progress=on_progress,
        expected_override=expected,
    )
    result = reader.run()
    if result.stopped:
        if result.members:
            progress.update(members=result.members, expected=result.expected, complete=False)
            progress["pending"] = progress["pending"] or len(result.members) != before
            store.save_members(data_dir, progress)
            log.warn(
                f"已依要求停止。目前讀到 {len(result.members)} 人，已存在本機；"
                "之後可以執行「補讀缺少的成員」接著讀，或直接「上傳讀取結果」。"
            )
        else:
            log.warn("已依要求停止。")
        return False
    if result.stop_reason and result.expected is None:
        save_debug_image(data_dir, reader.last_image)
        log.error(result.stop_reason)
        return False
    if result.members:
        changed = len(result.members) != before or result.complete != progress["complete"]
        progress.update(members=result.members, expected=result.expected, complete=result.complete)
        progress["pending"] = progress["pending"] or changed
        store.save_members(data_dir, progress)

    if result.stop_reason:
        if not result.complete and "少" not in result.stop_reason:
            save_debug_image(data_dir, reader.last_image)
        log.warn(result.stop_reason)
    if resume:
        log.info(f"這次補讀到 {len(result.members) - before} 人。")
    summary = f"目前讀到 {len(result.members)} / {result.expected} 人" + (
        f"，{result.failed_rows} 列讀取失敗" if result.failed_rows else ""
    )
    if result.complete:
        log.success(f"{summary}，已讀完。請執行「上傳讀取結果」。")
    elif result.members:
        log.warn(
            f"{summary}，還沒讀完。可以執行「補讀缺少的成員」再找一次；"
            "也可以直接「上傳讀取結果」（當作未讀完，不會把沒讀到的人標為離開）。"
        )
    return bool(result.members)


class ReadMembersAction(CustomAction):
    """讀取家族成員並存在本機。discard：任務選項「捨棄本機結果重新讀取」為「是」。"""

    def __init__(self, discard: bool = False):
        super().__init__()
        self.discard = discard

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        data_dir = project_root() / "data"
        return read_members(MaaDevice(context), data_dir, parse_expected(argv), resume=False, discard=self.discard)


class ReadMissingMembersAction(CustomAction):
    """補讀缺少的成員：接續本機進度，從最上面滑到底，只讀還沒讀過的列。"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        return read_members(MaaDevice(context), project_root() / "data", parse_expected(argv), resume=True)
