"""「讀取深淵排行」：只讀取並存在本機，由「上傳讀取結果」任務上傳。

不 import AgentServer：MFAAvalonia 的 agent（actions.py）與開發工具（tools/dev_run.py）都呼叫這裡。
載入 AgentServer 後 MaaFramework 會進入 agent 模式，開發工具就不能自己連模擬器。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from maa.context import Context
from maa.custom_action import CustomAction

import local_results as store
from abyss_flow import AbyssReader, build_upload
from kumi_reader import log
from kumi_reader.device import Device, MaaDevice
from kumi_reader.session import project_root


def read_abyss(device: Device, data_dir: Path, now: datetime | None = None) -> bool:
    previous = store.load_abyss(data_dir)
    if previous is not None:
        log.warn(f"本機有一份還沒上傳的深淵排行（{len(previous['body']['rows'])} 名），這次的結果會取代它。")
    log.info("開始讀取深淵排行…")
    result = AbyssReader(device).run()
    if result.stop_reason and not result.rows:
        log.error(result.stop_reason)
        return False
    if result.stop_reason:
        log.warn(result.stop_reason)
    store.save_abyss(data_dir, build_upload(result, None), now or datetime.now(timezone.utc))
    if result.complete:
        log.success(f"讀到 {len(result.rows)} 名，已讀完。請執行「上傳讀取結果」。")
    else:
        log.warn(f"讀到 {len(result.rows)} 名，沒有讀完。可以再讀一次，或直接「上傳讀取結果」（之後再讀會接續同一批次）。")
    return True


class ReadAbyssAction(CustomAction):
    """讀取深淵排行並存在本機。"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        return read_abyss(MaaDevice(context), project_root() / "data")
