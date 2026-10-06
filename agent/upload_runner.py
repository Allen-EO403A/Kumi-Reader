"""「上傳讀取結果」：把本機還沒上傳的家族成員與深淵排行結果上傳。

上傳失敗時本機結果保留，下次再執行這個任務即可；不用重新讀取。
不 import AgentServer（理由同 members_runner.py）。
"""
from __future__ import annotations

from pathlib import Path

from maa.context import Context
from maa.custom_action import CustomAction

import local_results as store
from kumi_reader import log
from kumi_reader.api import ApiError
from kumi_reader.session import Session, project_root, start_session
from members_flow import MembersResult
from members_flow import build_upload as build_members_upload


def upload_all(root: Path) -> bool:
    data_dir = root / "data"
    progress = store.load_members(data_dir)
    members_pending = progress is not None and progress["pending"] and bool(progress["members"])
    abyss = store.load_abyss(data_dir)
    if not members_pending and abyss is None:
        log.warn("本機沒有還沒上傳的讀取結果。請先執行「讀取家族成員」或「讀取深淵排行」。")
        return False
    ok = True
    if members_pending:
        session = start_session("members", root)
        ok = session is not None and upload_members(session, progress) and ok
    if abyss is not None:
        session = start_session("abyss", root)
        ok = session is not None and upload_abyss(session, abyss) and ok
    return ok


def upload_members(session: Session, progress: dict) -> bool:
    result = MembersResult(expected=progress["expected"], members=progress["members"], complete=progress["complete"])
    batch_id = progress["batchId"]
    body = build_members_upload(result, batch_id)
    log.info(f"上傳家族成員：{len(result.members)} / {result.expected} 人" + ("（已讀完）" if result.complete else "（未讀完）"))
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
        log.error(f"{err.describe()} 讀取結果仍保留在本機，可以稍後再執行「上傳讀取結果」。")
        return False

    if res["status"] == "incomplete":
        progress.update(batchId=res["batchId"], pending=False)
        store.save_members(session.data_dir, progress)
        log.warn("這次上傳的是未讀完的結果，不會把沒讀到的人標為離開。補讀後再上傳會接續同一批次。")
    else:
        store.clear_members(session.data_dir)
    log.success(
        f"已上傳家族成員：實讀 {res['readCount']} / 應讀 {res['expectedCount']} 人；"
        f"新成員 {res['newMembers']}、改名 {res['renamed']}、重新入族 {res['rejoined']}、"
        f"標為離開 {res['markedLeft']}、讀不出暱稱 {res['nameUnreadable']}。"
    )
    if res.get("countMismatch"):
        log.warn("實讀人數與應讀人數不符，請到網站確認。")
    return True


def upload_abyss(session: Session, saved: dict) -> bool:
    try:
        current = session.api.current_abyss_batch()
    except ApiError as err:
        log.error(f"{err.describe()} 讀取結果仍保留在本機，可以稍後再執行「上傳讀取結果」。")
        return False
    if current["periodStart"] != saved["periodStart"]:
        # 上傳時才決定批次歸屬：跨週期上傳會把舊排行算進新週期，所以不上傳
        store.clear_abyss(session.data_dir)
        log.error(
            f"本機的深淵排行是 {saved['periodStart']} 起的深淵週期讀到的，現在已是 {current['periodStart']} 起的週期，"
            "無法上傳，已捨棄這份結果。"
        )
        return False
    batch_id = current.get("batchId")
    body = dict(saved["body"])
    if batch_id:
        body["batchId"] = batch_id
        log.info(f"本週期有未完成的批次（讀到第 {current.get('lastRank')} 名），這次的結果會接續合併。")
    log.info(f"上傳深淵排行：{len(body['rows'])} 名。")
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
        log.error(f"{err.describe()} 讀取結果仍保留在本機，可以稍後再執行「上傳讀取結果」。")
        return False

    store.clear_abyss(session.data_dir)
    if res["status"] == "incomplete":
        log.warn("這次上傳的是沒讀完的排行。下一個週五 20:00（排行清空）前再讀一次並上傳，會接續同一批次。")
    log.success(
        f"已上傳深淵排行（{res['periodStart']} 起的深淵週期）：新增 {res['inserted']} 列、取代 {res['replaced']} 列；"
        f"對上 {res['matched']}、對不到 {res['unmatched']}、有疑義 {res['ambiguous']}。請到網站「深淵審核」確認。"
    )
    if res.get("skippedConfirmed"):
        log.info(f"已確認的 {res['skippedConfirmed']} 列沒有變更。")
    return True


class UploadAction(CustomAction):
    """上傳本機還沒上傳的讀取結果。"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        return upload_all(project_root())
