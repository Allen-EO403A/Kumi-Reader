"""每次執行開始時的共同步驟：讀設定、確認金鑰（並綁定這一份程式）、重送本機暫存。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import log
from .api import ApiError, KumiApi, Program
from .config import ConfigError, load_config
from .instance import load_or_create_instance_id
from .outbox import Outbox

PROGRAM_LABELS = {"members": "家族成員", "abyss": "深淵排行"}


@dataclass
class Session:
    api: KumiApi
    outbox: Outbox
    data_dir: Path


def project_root() -> Path:
    """程式資料夾：agent/ 的上一層（開發時是 repo 根目錄，安裝後是 install/）。"""
    return Path(__file__).resolve().parents[2]


def start_session(program: Program, root: Path | None = None) -> Session | None:
    """成功回傳 Session；設定或金鑰有問題時顯示原因並回傳 None（不開始讀取）。"""
    root = root or project_root()
    data_dir = root / "data"
    try:
        config = load_config(root)
    except ConfigError as err:
        log.error(str(err))
        return None

    api = KumiApi(config.api_url, config.reader_key, program, load_or_create_instance_id(data_dir))
    try:
        me = api.whoami()
    except ApiError as err:
        if err.status == 401:
            log.error("讀取程式金鑰無效或已作廢。請向管理員取得新的金鑰，填入 .env 的 KUMI_READER_KEY。")
        else:
            log.error(err.describe())
        return None
    log.info(f"金鑰「{me.key_name}」已確認（{PROGRAM_LABELS[program]}讀取程式）。")

    outbox = Outbox(data_dir)
    if outbox.pending():
        sent, left = outbox.flush(lambda kind, body: _send(api, kind, body))
        if sent:
            log.success(f"已重送先前未上傳成功的結果 {sent} 筆。")
        if left:
            log.warn(f"還有 {left} 筆結果無法上傳（連不上後端），下次執行時會再試。")
    return Session(api=api, outbox=outbox, data_dir=data_dir)


def _send(api: KumiApi, kind: str, body: dict):
    if kind == "member-batch":
        return api.upload_member_batch(body)
    if kind == "abyss-batch":
        return api.upload_abyss_batch(body)
    raise ValueError(f"未知的暫存種類：{kind}")
