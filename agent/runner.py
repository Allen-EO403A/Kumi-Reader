"""「讀取家族成員並上傳」的完整流程。

不 import AgentServer：MFAAvalonia 的 agent（actions.py）與開發工具（tools/dev_run.py）都呼叫這裡。
載入 AgentServer 後 MaaFramework 會進入 agent 模式，開發工具就不能自己連模擬器。
"""
from __future__ import annotations

import json

from maa.context import Context
from maa.custom_action import CustomAction

from kumi_reader import log
from kumi_reader.api import ApiError
from kumi_reader.device import MaaDevice
from kumi_reader.session import Session, start_session
from members_flow import MembersReader, MembersResult, build_upload

# 未完成的批次 ID：下次執行時接續（後端以 UID 去重合併）
PENDING_BATCH_FILE = "member-batch.json"


class ReadMembersAction(CustomAction):
    """讀取家族成員並上傳。"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        session = start_session("members")
        if session is None:
            return False
        log.info("開始讀取家族成員…")
        result = MembersReader(MaaDevice(context)).run()
        if result.stop_reason and not result.members:
            log.error(result.stop_reason)
            return False
        if result.stop_reason:
            log.warn(result.stop_reason)
        return upload(session, result)


def upload(session: Session, result: MembersResult) -> bool:
    state_file = session.data_dir / PENDING_BATCH_FILE
    batch_id = json.loads(state_file.read_text(encoding="utf-8"))["batchId"] if state_file.exists() else None
    body = build_upload(result, batch_id)
    log.info(f"讀到 {len(result.members)} 人（應讀 {result.expected} 人）" + (f"，{result.failed_rows} 列讀取失敗" if result.failed_rows else ""))
    try:
        try:
            res = session.api.upload_member_batch(body)
        except ApiError as err:
            if batch_id is None or err.status not in (404, 409):
                raise
            # 先前的批次已完成或不存在：改為新批次
            body.pop("batchId")
            res = session.api.upload_member_batch(body)
    except ApiError as err:
        if err.retryable:
            session.outbox.save("member-batch", body)
            log.warn(f"{err.describe()} 結果已存在本機，下次執行時會自動重送。")
        else:
            log.error(err.describe())
        return False

    if res["status"] == "incomplete":
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({"batchId": res["batchId"]}), encoding="utf-8")
        log.warn("這次沒有讀完，已上傳讀到的部分。下次執行時會接續同一批次。")
    else:
        state_file.unlink(missing_ok=True)
    log.success(
        f"已上傳家族成員：實讀 {res['readCount']} / 應讀 {res['expectedCount']} 人；"
        f"新成員 {res['newMembers']}、改名 {res['renamed']}、重新入族 {res['rejoined']}、"
        f"標為離開 {res['markedLeft']}、讀不出暱稱 {res['nameUnreadable']}。"
    )
    if res.get("countMismatch"):
        log.warn("實讀人數與應讀人數不符，請到網站確認。")
    return True
