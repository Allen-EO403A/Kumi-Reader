# Kumi Reader - 讀取「忍者必須死」家族成員與深淵排行並上傳到 Kumi
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

"""上傳失敗時的本機暫存：結果先存檔，下次啟動時依序重送，避免重新讀取。

只有連線問題或伺服器錯誤（可重送）才暫存；格式錯誤等重送也不會成功的錯誤，
檔案移到 failed/ 保留，交給管理員查看。
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .api import ApiError


class Outbox:
    def __init__(self, data_dir: Path):
        self.dir = data_dir / "outbox"
        self.failed_dir = self.dir / "failed"

    def save(self, kind: str, body: dict[str, Any]) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        # 檔名以遞增的序號開頭，依檔名排序即為儲存順序
        seq = max((int(p.name.split("-", 1)[0]) for p in self.pending()), default=time.time_ns()) + 1
        seq = max(seq, time.time_ns())
        path = self.dir / f"{seq:020d}-{kind}.json"
        path.write_text(json.dumps({"kind": kind, "body": body}, ensure_ascii=False), encoding="utf-8")
        return path

    def pending(self) -> list[Path]:
        return sorted(self.dir.glob("*.json")) if self.dir.exists() else []

    def flush(self, send: Callable[[str, dict[str, Any]], Any]) -> tuple[int, int]:
        """依時間順序重送。遇到可重送的錯誤就停（保留後面的順序）。回傳（成功數、剩下數）。"""
        sent = 0
        for path in self.pending():
            item = json.loads(path.read_text(encoding="utf-8"))
            try:
                send(item["kind"], item["body"])
            except ApiError as err:
                if err.retryable:
                    return sent, len(self.pending())
                self.failed_dir.mkdir(parents=True, exist_ok=True)
                path.replace(self.failed_dir / path.name)
                continue
            path.unlink()
            sent += 1
        return sent, 0
