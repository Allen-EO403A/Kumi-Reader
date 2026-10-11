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

"""安裝識別碼：每份程式第一次啟動時產生，存在程式資料夾的 data/instance-id。

後端以它把讀取程式金鑰綁定到這一份程式（decisions.md 第 19 節）。
它不是憑證；刪掉這個檔案等於換了一份新安裝，原本的金鑰就不能再用。
"""
from __future__ import annotations

import uuid
from pathlib import Path


def load_or_create_instance_id(data_dir: Path) -> str:
    path = data_dir / "instance-id"
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        try:
            return str(uuid.UUID(value))
        except ValueError:
            pass  # 內容損壞時重新產生
    value = str(uuid.uuid4())
    data_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(value + "\n", encoding="utf-8")
    return value
