"""「設定金鑰（從剪貼簿）」：把網站複製的讀取程式金鑰寫進 .env（decisions.md 第 19 節）。

金鑰不經過 MFAAvalonia 的輸入欄位：欄位值會以明碼寫進 maafw.log（2026-10-05 實測），
所以改由程式直接讀剪貼簿、寫進 .env 後清除剪貼簿；執行紀錄只顯示金鑰開頭。
後端網址不是憑證，可以用 MFAAvalonia 的輸入欄位傳入。
"""
from __future__ import annotations

import ctypes
import json
import re
from pathlib import Path

from maa.context import Context
from maa.custom_action import CustomAction

from kumi_reader import log
from kumi_reader.config import KEY_PATTERN, ConfigError, load_config
from kumi_reader.session import project_root, start_session

CF_UNICODETEXT = 13


def read_clipboard() -> str:
    """讀取 Windows 剪貼簿的文字；沒有文字時回傳空字串。"""
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.GetClipboardData.restype = ctypes.c_void_p
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    if not user32.OpenClipboard(None):
        return ""
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        pointer = kernel32.GlobalLock(handle)
        try:
            return ctypes.wstring_at(pointer) if pointer else ""
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def clear_clipboard() -> None:
    user32 = ctypes.windll.user32
    if user32.OpenClipboard(None):
        try:
            user32.EmptyClipboard()
        finally:
            user32.CloseClipboard()


def mask(key: str) -> str:
    """執行紀錄只顯示金鑰開頭：「kumi_abcd1234_…」。"""
    return key[: len("kumi_") + 9] + "…"


def write_env(root: Path, key: str, api_url: str | None) -> None:
    """更新 .env 的 KUMI_READER_KEY（有填時也更新 KUMI_API_URL），其他行保留。"""
    path = root / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    values = {"KUMI_READER_KEY": key}
    if api_url:
        values["KUMI_API_URL"] = api_url
    out, seen = [], set()
    for line in lines:
        name = line.split("=", 1)[0].strip()
        if name in values:
            out.append(f"{name}={values[name]}")
            seen.add(name)
        else:
            out.append(line)
    out += [f"{name}={value}" for name, value in values.items() if name not in seen]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def setup_key(root: Path, clipboard: str, api_url: str | None) -> bool:
    key = clipboard.strip()
    if not KEY_PATTERN.match(key):
        log.error("剪貼簿裡沒有讀取程式金鑰。請在網站「讀取程式金鑰」頁產生金鑰並按「複製」後，再執行這個任務。")
        return False
    if api_url and not re.match(r"^https?://", api_url):
        log.error("後端網址必須以 https:// 開頭。")
        return False
    write_env(root, key, api_url.rstrip("/") if api_url else None)
    log.success(f"已設定金鑰 {mask(key)}，並清除剪貼簿。")
    try:
        load_config(root)
    except ConfigError as err:
        log.warn(str(err))
        return False
    return True


class SetKeyAction(CustomAction):
    """設定金鑰（從剪貼簿）並確認可以連上後端。"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        try:
            api_url = str(json.loads(argv.custom_action_param or "{}").get("apiUrl", "")).strip()
        except ValueError:
            api_url = ""
        root = project_root()
        ok = setup_key(root, read_clipboard(), api_url or None)
        clear_clipboard()
        if not ok:
            return False
        # 確認金鑰有效（第一次使用時同時綁定這一份程式的家族成員讀取）
        return start_session("members", root) is not None
