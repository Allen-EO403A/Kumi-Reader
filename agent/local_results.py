"""讀取結果的本機存檔：讀取任務只存檔，「上傳讀取結果」任務再上傳（decisions.md 第 19 節）。

不 import MaaFramework，方便單元測試。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 家族成員：批次 ID（上傳過未讀完時）、已讀成員、已處理的列、應讀人數、是否讀完、是否還沒上傳
MEMBERS_FILE = "members-progress.json"
# 深淵排行：讀取時間、所屬深淵週期、上傳內容（不含 batchId）
ABYSS_FILE = "abyss-result.json"

TAIPEI = timezone(timedelta(hours=8))


def load_members(data_dir: Path) -> dict | None:
    path = data_dir / MEMBERS_FILE
    if not path.exists():
        return None
    progress = json.loads(path.read_text(encoding="utf-8"))
    progress.setdefault("batchId", None)
    progress.setdefault("members", {})
    progress.setdefault("doneKeys", [])
    progress.setdefault("expected", None)
    progress.setdefault("complete", False)
    progress.setdefault("pending", False)  # 0.2 版的進度檔都已上傳過
    return progress


def new_members_progress() -> dict:
    return {"batchId": None, "members": {}, "doneKeys": [], "expected": None, "complete": False, "pending": False}


def save_members(data_dir: Path, progress: dict) -> None:
    _write(data_dir / MEMBERS_FILE, progress)


def clear_members(data_dir: Path) -> None:
    (data_dir / MEMBERS_FILE).unlink(missing_ok=True)


def load_abyss(data_dir: Path) -> dict | None:
    path = data_dir / ABYSS_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def save_abyss(data_dir: Path, body: dict, read_at: datetime) -> None:
    _write(
        data_dir / ABYSS_FILE,
        {"readAt": read_at.isoformat(), "periodStart": abyss_period_start(read_at), "body": body},
    )


def clear_abyss(data_dir: Path) -> None:
    (data_dir / ABYSS_FILE).unlink(missing_ok=True)


def abyss_period_start(at: datetime) -> str:
    """深淵週期：週五 20:00（台灣時間）到下一個週五 20:00，以該週五的台灣日期表示（與後端相同）。"""
    local = at.astimezone(TAIPEI) - timedelta(hours=20)
    friday = local.date() - timedelta(days=(local.weekday() - 4) % 7)
    return friday.isoformat()


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
