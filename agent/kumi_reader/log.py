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
