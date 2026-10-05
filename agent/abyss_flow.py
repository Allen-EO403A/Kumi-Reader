"""程式 B：讀取深淵排行「家族狀況」分頁（reader.md、decisions.md 第 18、19 節）。

不點擊任何東西：先滑到最上面，然後逐頁讀取完整露出的每一列（暱稱、職位、傷害、挑戰次數），
往上滑，滑動後畫面不變代表到底。名次用名單中的順序（不讀金銀銅藝術字）；
底部固定的黃色列是執行帳號自己，不在可視範圍內。滑動後重複出現的列以「傷害＋挑戰次數」的順序對齊後略過。
座標為 1920×1080 原始解析度，取自 2026-10-03 實機截圖。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from kumi_reader.device import Device, Roi, region_changed
from kumi_reader.text import parse_int, parse_name, parse_role

LIST_TOP, LIST_BOTTOM = 143, 876  # 表頭下緣～黃色列上緣
SEPARATOR_X = (1180, 1330)  # 暱稱與傷害之間的空白欄
ROW_HEIGHT = 135
FAMILY_TAB_PIXEL = (900, 50)  # 「家族狀況」分頁：選取時為淺色
HEADER_ROI: Roi = (1380, 92, 120, 48)  # 欄位標題「傷害」


def row_name_roi(top: int) -> Roi:
    return (982, top + 19, 340, 56)


def row_role_roi(top: int) -> Roi:
    return (988, top + 73, 96, 46)


def row_damage_roi(top: int) -> Roi:
    return (1350, top + 43, 260, 56)


def row_challenges_roi(top: int) -> Roi:
    return (1700, top + 43, 140, 56)


# 拖曳後停住再放開（沒有慣性，距離固定；程式 A 實機量測：拖 340 px 移動 283～312 px）
DRAG_X = 1300
DRAG_FROM, DRAG_TO = 800, 350  # 往下捲約 3 列（畫面 5 列，前後重疊約 2 列）
DRAG_BACK = 180  # 沒有重疊時往回拖的距離（約 1.3 列）
TOP_FROM, TOP_TO = 260, 820  # 回到最上面
SETTLE_SECONDS = 0.6
LIST_REGION: Roi = (780, LIST_TOP, 1120, LIST_BOTTOM - LIST_TOP)


def find_row_tops(image: np.ndarray) -> list[int]:
    """完整露出的列：回傳每列上緣分隔線的 y。分隔線為深色（約 RGB 19,28,46）。"""
    x0, x1 = SEPARATOR_X
    brightness = image[LIST_TOP:LIST_BOTTOM + 4, x0:x1].astype(float).mean(axis=(1, 2))
    lines: list[int] = []
    for offset, value in enumerate(brightness):
        if value < 80:
            y = LIST_TOP + offset
            if not lines or y - lines[-1] > 20:
                lines.append(y)
    return [a for a, b in zip(lines, lines[1:]) if 110 <= b - a <= 160]


def on_family_tab(image: np.ndarray, header_text: str) -> bool:
    """在深淵排行且選的是「家族狀況」：表頭有「傷害」，且家族狀況分頁是淺色（選取中）。"""
    x, y = FAMILY_TAB_PIXEL
    return "傷害" in header_text and float(image[y, x].astype(float).mean()) > 170


@dataclass
class AbyssRow:
    rank: int
    name: str | None
    role: str | None
    damage: int
    challenges: int


@dataclass
class AbyssResult:
    rows: list[AbyssRow] = field(default_factory=list)
    complete: bool = False
    stop_reason: str | None = None


class AbyssReader:
    def __init__(self, device: Device, max_pages: int = 80, retries: int = 3):
        self.d = device
        self.max_pages = max_pages
        self.retries = retries

    def _drag(self, y1: int, y2: int) -> np.ndarray:
        self.d.drag(DRAG_X, y1, y2)
        self.d.sleep(SETTLE_SECONDS)
        return self.d.screencap()

    def _scroll_to_top(self, image: np.ndarray) -> np.ndarray:
        for _ in range(self.max_pages):
            after = self._drag(TOP_FROM, TOP_TO)
            if not region_changed(image, after, LIST_REGION):
                return after
            image = after
        return image

    def _read_row(self, image: np.ndarray, top: int) -> tuple[str, int, int, str] | None:
        """回傳（暱稱原文、傷害、挑戰次數、職位原文）；數值讀不出來時重新截圖再讀。"""
        for attempt in range(self.retries):
            if attempt:
                self.d.sleep(0.3)
                image = self.d.screencap()
            damage = parse_int(self.d.ocr(image, row_damage_roi(top)))
            challenges = parse_int(self.d.ocr(image, row_challenges_roi(top)))
            if damage is not None and challenges is not None:
                return (
                    self.d.ocr(image, row_name_roi(top)),
                    damage,
                    challenges,
                    self.d.ocr(image, row_role_roi(top)),
                )
        return None

    @staticmethod
    def _overlap(result: AbyssResult, page: list[tuple[str, int, int, str]]) -> int:
        """這一頁開頭與已讀名單結尾重疊的列數。

        以「傷害＋挑戰次數」的順序對齊（數字的 OCR 最穩定）：找已讀名單結尾與這一頁開頭
        最長的相同序列。不用暱稱比對，避免同一列兩次讀得不一樣時名次錯位。
        """
        numbers = [(r.damage, r.challenges) for r in result.rows]
        incoming = [(damage, challenges) for _, damage, challenges, _ in page]
        for k in range(min(len(numbers), len(incoming)), 0, -1):
            if numbers[-k:] == incoming[:k]:
                return k
        return 0

    @staticmethod
    def _append(result: AbyssResult, rows: list[tuple[str, int, int, str]]) -> None:
        for name_text, damage, challenges, role_text in rows:
            result.rows.append(
                AbyssRow(
                    rank=len(result.rows) + 1,
                    name=parse_name(name_text),
                    role=parse_role(role_text),
                    damage=damage,
                    challenges=challenges,
                )
            )

    def _read_page(self, image: np.ndarray) -> tuple[list[tuple[str, int, int, str]], bool]:
        """讀這一頁完整露出的列；遇到數字讀不出來的列就停在那裡（回傳 failed=True）。"""
        page = []
        for top in find_row_tops(image):
            row = self._read_row(image, top)
            if row is None:
                return page, True
            page.append(row)
        return page, False

    def run(self) -> AbyssResult:
        result = AbyssResult()
        image = self.d.screencap()
        if not on_family_tab(image, self.d.ocr(image, HEADER_ROI)):
            result.stop_reason = "目前不在深淵排行的「家族狀況」分頁。請打開「家族狀況」分頁後再執行。"
            return result
        image = self._scroll_to_top(image)

        first_page = True
        for _page in range(self.max_pages):
            page, failed = self._read_page(image)
            overlap = 0
            if not first_page:
                overlap = self._overlap(result, page)
                for _ in range(self.retries):
                    if overlap:
                        break
                    # 與上一頁沒有重疊：可能滑過頭，往回拖再讀
                    image = self._drag(DRAG_TO, DRAG_TO + DRAG_BACK)
                    page, failed = self._read_page(image)
                    overlap = self._overlap(result, page)
                if not overlap:
                    result.stop_reason = "滑動後找不到與上一頁重疊的列，為避免名次錯位已停止，已讀部分存在本機。"
                    return result
            self._append(result, page[overlap:])
            if failed:
                result.stop_reason = f"第 {len(result.rows) + 1} 名的傷害或挑戰次數讀不出來，已停止，已讀部分存在本機。"
                return result
            first_page = False
            before = image
            image = self._drag(DRAG_FROM, DRAG_TO)
            if not region_changed(before, image, LIST_REGION):
                result.complete = True  # 滑動後畫面不變：已到底
                return result
        result.stop_reason = "讀取頁數超過上限，已停止，已讀部分存在本機。"
        return result


def build_upload(result: AbyssResult, batch_id: int | None) -> dict:
    body: dict = {
        "status": "complete" if result.complete else "incomplete",
        "lastRank": len(result.rows),
        "rows": [
            {
                "rank": r.rank,
                "name": r.name,
                "role": r.role,
                "damage": r.damage,
                "challengeCount": r.challenges,
            }
            for r in result.rows
        ],
    }
    if batch_id is not None:
        body["batchId"] = batch_id
    return body
