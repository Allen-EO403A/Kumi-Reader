"""「讀取深淵排行並上傳」的完整流程。

不 import AgentServer：MFAAvalonia 的 agent（actions.py）與開發工具（tools/dev_run.py）都呼叫這裡。
載入 AgentServer 後 MaaFramework 會進入 agent 模式，開發工具就不能自己連模擬器。
"""
from __future__ import annotations

from maa.context import Context
from maa.custom_action import CustomAction

from abyss_flow import AbyssReader, AbyssResult, build_upload
from kumi_reader import log
from kumi_reader.api import ApiError
from kumi_reader.device import MaaDevice
from kumi_reader.session import Session, start_session


class ReadAbyssAction(CustomAction):
    """讀取深淵排行並上傳。"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        session = start_session("abyss")
        if session is None:
            return False
        try:
            current = session.api.current_abyss_batch()
        except ApiError as err:
            log.error(err.describe())
            return False
        batch_id = current.get("batchId")
        if batch_id:
            log.info(f"本週期有未完成的批次（讀到第 {current.get('lastRank')} 名），這次的結果會接續合併。")
        log.info("開始讀取深淵排行…")
        result = AbyssReader(MaaDevice(context)).run()
        if result.stop_reason and not result.rows:
            log.error(result.stop_reason)
            return False
        if result.stop_reason:
            log.warn(result.stop_reason)
        return upload(session, result, batch_id)


def upload(session: Session, result: AbyssResult, batch_id: int | None) -> bool:
    body = build_upload(result, batch_id)
    log.info(f"讀到 {len(result.rows)} 名。")
    try:
        try:
            res = session.api.upload_abyss_batch(body)
        except ApiError as err:
            if batch_id is None or err.status not in (404, 409):
                raise
            # 先前的批次已完成或不屬於本週期：改為本週期的新批次（或重跑）
            body.pop("batchId")
            res = session.api.upload_abyss_batch(body)
    except ApiError as err:
        if err.retryable:
            session.outbox.save("abyss-batch", body)
            log.warn(f"{err.describe()} 結果已存在本機，下次執行時會自動重送。")
        else:
            log.error(err.describe())
        return False

    if res["status"] == "incomplete":
        log.warn("這次沒有讀完，已上傳讀到的部分。排行清空前再執行一次會接續同一批次。")
    log.success(
        f"已上傳深淵排行（{res['periodStart']} 起的深淵週期）：新增 {res['inserted']} 列、取代 {res['replaced']} 列；"
        f"對上 {res['matched']}、對不到 {res['unmatched']}、有疑義 {res['ambiguous']}。請到網站「深淵審核」確認。"
    )
    if res.get("skippedConfirmed"):
        log.info(f"已確認的 {res['skippedConfirmed']} 列沒有變更。")
    return True
