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

"""輸出給 MFAAvalonia 的執行紀錄。

MFAAvalonia 只把 `info:`、`warn:`、`err:`、`success:` 等前綴的行顯示在介面上，
其他行只寫進它的紀錄檔。這裡統一加前綴；呼叫端不得把金鑰放進訊息。
"""
from __future__ import annotations

import sys


def _emit(prefix: str, message: str) -> None:
    for line in str(message).splitlines() or [""]:
        print(f"{prefix}:{line}", flush=True)


def info(message: str) -> None:
    _emit("info", message)


def warn(message: str) -> None:
    _emit("warn", message)


def error(message: str) -> None:
    _emit("err", message)


def success(message: str) -> None:
    _emit("success", message)


def debug(message: str) -> None:
    """除錯訊息：只進紀錄檔，不顯示在介面上。"""
    print(message, file=sys.stderr, flush=True)
