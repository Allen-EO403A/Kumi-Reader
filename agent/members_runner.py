"""「讀取家族成員並上傳」的完整流程。

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

from kumi_reader import log
from kumi_reader.api import ApiError
from kumi_reader.device import MaaDevice
from kumi_reader.session import Session, start_session
from members_flow import MembersReader, MembersResult, build_upload

# 未讀完時的進度：批次 ID、已讀成員、已處理的列。下次執行接續，已讀的人不再開個人視窗。
PROGRESS_FILE = "members-progress.json"


def load_progress(data_dir: Path) -> dict:
    path = data_dir / PROGRESS_FILE
    if not path.exists():
        return {"batchId": None, "members": {}, "doneKeys": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_progress(data_dir: Path, progress: dict) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / PROGRESS_FILE).write_text(json.dumps(progress, ensure_ascii=False), encoding="utf-8")


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


def read_and_upload(context: Context, argv: CustomAction.RunArg, page_only: bool) -> bool:
    session = start_session("members")
    if session is None:
        return False
    progress = load_progress(session.data_dir)
    if page_only and not progress["members"]:
        log.warn("沒有接續中的批次。補讀會建立新的批次；平常請先執行「讀取家族成員」。")
    elif progress["members"]:
        log.info(f"接續上次的進度：已讀 {len(progress['members'])} 人，這次只讀還沒讀過的。")
    log.info("開始補讀目前畫面…" if page_only else "開始讀取家族成員…")

    def on_progress(result: MembersResult, done: set) -> None:
        progress["members"] = result.members
        progress["doneKeys"] = [list(k) for k in done]
        save_progress(session.data_dir, progress)

    reader = MembersReader(
        MaaDevice(context),
        done_keys={tuple(k) for k in progress["doneKeys"]},
        known=progress["members"],
        on_progress=on_progress,
        expected_override=parse_expected(argv),
    )
    result = reader.run_page() if page_only else reader.run()
    if result.stop_reason and result.expected is None:
        save_debug_image(session.data_dir, reader.last_image)
        log.error(result.stop_reason)
        return False
    if result.stop_reason:
        if not result.complete and "少" not in result.stop_reason:
            save_debug_image(session.data_dir, reader.last_image)
        log.warn(result.stop_reason)
    if not result.members:
        return False
    ok = upload(session, result, progress)
    if ok and not result.complete:
        log.warn("請把名單移到缺少成員所在的那一頁，執行「補讀目前畫面」。")
    return ok


class ReadMembersAction(CustomAction):
    """讀取家族成員並上傳。"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        return read_and_upload(context, argv, page_only=False)


class ReadMembersPageAction(CustomAction):
    """補讀目前畫面並上傳到同一批次。"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        return read_and_upload(context, argv, page_only=True)


def upload(session: Session, result: MembersResult, progress: dict) -> bool:
    batch_id = progress.get("batchId")
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
        progress["batchId"] = res["batchId"]
        save_progress(session.data_dir, progress)
        log.warn("這次沒有讀完，已上傳讀到的部分。下次執行時會接續，已讀的人不會重讀。")
    else:
        (session.data_dir / PROGRESS_FILE).unlink(missing_ok=True)
    log.success(
        f"已上傳家族成員：實讀 {res['readCount']} / 應讀 {res['expectedCount']} 人；"
        f"新成員 {res['newMembers']}、改名 {res['renamed']}、重新入族 {res['rejoined']}、"
        f"標為離開 {res['markedLeft']}、讀不出暱稱 {res['nameUnreadable']}。"
    )
    if res.get("countMismatch"):
        log.warn("實讀人數與應讀人數不符，請到網站確認。")
    return True
