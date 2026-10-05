"""OCR 結果的清理與格式檢查（兩支程式共用的部分）。"""
from __future__ import annotations

import re
import unicodedata

# 遊戲中出現的族內職位（取自畫面原型與截圖）
ROLES = ("族長", "副族長", "長老", "精英", "豪傑", "族員", "新人")


def _halfwidth(text: str) -> str:
    """全形英數與標點轉半形；不動中日文字與「・」等符號（所以不用 NFKC）。"""
    return "".join(chr(ord(ch) - 0xFEE0) if 0xFF01 <= ord(ch) <= 0xFF5E else ch for ch in text)


def clean(text: str) -> str:
    """去掉零寬等格式字元與前後空白，全形英數轉半形。"""
    return _halfwidth("".join(ch for ch in text if unicodedata.category(ch) != "Cf")).strip()


def parse_uid(text: str) -> str | None:
    """從「ID：271203460345」取出 12 碼 UID：整段文字中必須剛好有一段 12 碼數字。

    不靠刪除「ID」前綴（OCR 偶爾把 ID 讀成 1D，刪前綴會誤刪 UID 開頭的 1）。
    """
    runs = re.findall(r"\d+", _halfwidth(text).replace(" ", ""))
    found = [run for run in runs if len(run) == 12]
    return found[0] if len(found) == 1 and not any(len(r) > 12 for r in runs) else None


def parse_int(text: str) -> int | None:
    """整串都是數字才接受（傷害、挑戰次數、人數）。"""
    value = _halfwidth(text).replace(",", "").replace(" ", "").strip()
    return int(value) if re.fullmatch(r"\d+", value) else None


def parse_member_count(text: str) -> tuple[int, int] | None:
    """「成員：99/100」→（99, 100）。"""
    match = re.search(r"(\d+)\s*/\s*(\d+)", _halfwidth(text))
    return (int(match.group(1)), int(match.group(2))) if match else None


def parse_role(text: str) -> str | None:
    """OCR 讀到的職位：完全符合或包含已知職位時採用，否則 None。"""
    value = clean(text)
    if value in ROLES:
        return value
    # 「副族長」包含「族長」，所以由長到短比對
    for role in sorted(ROLES, key=len, reverse=True):
        if role in value:
            return role
    return None


def strip_remark(text: str) -> str:
    """去掉括號開始的備註：「凌汐雪(小戌時)」→「凌汐雪」。

    備註是執行帳號自己替別人設定的，每個帳號都不同，只取括號前面的暱稱（2026-10-05 使用者決定）。
    半形與全形括號都算；括號沒有收尾（被截斷）也一樣去掉。
    """
    for mark in ("(", "（"):
        index = text.find(mark)
        if index > 0:
            text = text[:index]
    return text.strip()


def parse_name(text: str) -> str | None:
    """暱稱：清理並去掉括號備註後非空就採用；讀不出來時為 None，由後端標為需手動命名。"""
    value = strip_remark(clean(text))
    return value or None
