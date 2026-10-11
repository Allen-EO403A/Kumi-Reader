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

"""程式 B：讀取深淵排行「家族狀況」分頁（reader.md、decisions.md 第 18、19 節）。

不點擊任何東西：先滑到最上面，然後逐頁讀取完整露出的每一列（名次、暱稱、職位、傷害、挑戰次數），
往上滑，滑動後畫面不變代表到底。名次以每列左側的名次數字為準（2026-10-05 起），
前後頁以名次合併；新的一頁和已讀名次之間有缺號時往回拖重讀，避免漏掉。
讀不出名次的列（例如前三名的金銀銅圖示）依同一頁其他列的名次推算；整頁都讀不出時，
以「傷害＋挑戰次數」與已讀名單對齊。底部固定的黃色列是執行帳號自己，不在可視範圍內。
座標為 1920×1080 原始解析度，取自 2026-10-03 實機截圖。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from kumi_reader.device import Device, Roi, StopRequested, region_changed
from kumi_reader.text import parse_int, parse_name, parse_role

LIST_TOP, LIST_BOTTOM = 143, 876  # 表頭下緣～黃色列上緣
# 用來找分隔線的空白欄：傷害與挑戰次數之間、面板右緣，兩欄都要是深色才算分隔線。
# 不用暱稱右邊的空白：長暱稱會延伸進去（家族成員列表曾因此跳過整列，2026-10-05）。
SEPARATOR_BANDS = ((1620, 1680), (1850, 1900))
ROW_HEIGHT = 135
TOP_ROW_SLACK = 12  # 第 1 名的上緣被表頭蓋住的容許量（實機約 8 px）
FAMILY_TAB_PIXEL = (900, 50)  # 「家族狀況」分頁：選取時為淺色
HEADER_ROI: Roi = (1380, 92, 120, 48)  # 欄位標題「傷害」


def row_rank_roi(top: int) -> Roi:
    return (785, top + 35, 95, 70)


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
    """完整露出的列：回傳每列上緣的 y。分隔線為深色（約 RGB 19,28,46）。"""
    dark = np.ones(LIST_BOTTOM + 4 - LIST_TOP, dtype=bool)
    for x0, x1 in SEPARATOR_BANDS:
        dark &= image[LIST_TOP:LIST_BOTTOM + 4, x0:x1].astype(float).mean(axis=(1, 2)) < 80
    lines: list[int] = []
    for offset, is_dark in enumerate(dark):
        if is_dark:
            y = LIST_TOP + offset
            if not lines or y - lines[-1] > 20:
                lines.append(y)
    tops = [a for a, b in zip(lines, lines[1:]) if 110 <= b - a <= 160]
    # 名單在最上面時，第 1 名上方是表頭、沒有深色分隔線：從第一條分隔線往上推一列
    # （2026-10-05 實機：沒有這一步時第 1 名整列被跳過）
    if lines and lines[0] - ROW_HEIGHT >= LIST_TOP - TOP_ROW_SLACK:
        tops.insert(0, lines[0] - ROW_HEIGHT)
    return tops


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
class PageRow:
    """畫面上讀到的一列（名次還沒確定）。"""

    rank: int | None
    name_text: str
    role_text: str
    damage: int
    challenges: int


@dataclass
class AbyssResult:
    rows: list[AbyssRow] = field(default_factory=list)
    complete: bool = False
    stop_reason: str | None = None
    stopped: bool = False  # 使用者按了停止


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

    def _read_row(self, image: np.ndarray, top: int) -> PageRow | None:
        """讀一列；傷害或挑戰次數讀不出來時重新截圖再讀。名次讀不出來時為 None（之後推算）。"""
        for attempt in range(self.retries):
            if attempt:
                self.d.sleep(0.3)
                image = self.d.screencap()
            damage = parse_int(self.d.ocr(image, row_damage_roi(top)))
            challenges = parse_int(self.d.ocr(image, row_challenges_roi(top)))
            if damage is not None and challenges is not None:
                return PageRow(
                    rank=parse_int(self.d.ocr(image, row_rank_roi(top))),
                    name_text=self.d.ocr(image, row_name_roi(top)),
                    role_text=self.d.ocr(image, row_role_roi(top)),
                    damage=damage,
                    challenges=challenges,
                )
        return None

    @staticmethod
    def _page_base(result: AbyssResult, page: list[PageRow], at_top: bool) -> int | None:
        """這一頁第一列的名次。

        以讀得出的名次推算（名次減去在頁中的位置，取最多列一致的值；個別讀錯的名次會被蓋過）。
        整頁都讀不出名次時：在名單最上面就是第 1 名，否則以「傷害＋挑戰次數」與已讀名單結尾對齊。
        """
        bases = [r.rank - i for i, r in enumerate(page) if r.rank is not None and r.rank >= 1]
        if bases:
            return Counter(bases).most_common(1)[0][0]
        if at_top:
            return 1
        numbers = [(r.damage, r.challenges) for r in result.rows]
        incoming = [(r.damage, r.challenges) for r in page]
        for k in range(min(len(numbers), len(incoming)), 0, -1):
            if numbers[-k:] == incoming[:k]:
                return len(result.rows) - k + 1
        return None

    @staticmethod
    def _append(result: AbyssResult, page: list[PageRow], base: int) -> None:
        """加入名次大於已讀最後名次的列（重複出現的列略過）。"""
        for i, r in enumerate(page):
            rank = base + i
            if rank <= len(result.rows):
                continue
            result.rows.append(
                AbyssRow(
                    rank=rank,
                    name=parse_name(r.name_text),
                    role=parse_role(r.role_text),
                    damage=r.damage,
                    challenges=r.challenges,
                )
            )

    def _read_page(self, image: np.ndarray) -> tuple[list[PageRow], bool]:
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
        try:
            return self._run(result)
        except StopRequested:
            result.complete = False
            result.stopped = True
            result.stop_reason = "已依要求停止。"
            return result

    def _run(self, result: AbyssResult) -> AbyssResult:
        image = self.d.screencap()
        if not on_family_tab(image, self.d.ocr(image, HEADER_ROI)):
            result.stop_reason = "目前不在深淵排行的「家族狀況」分頁。請打開「家族狀況」分頁後再執行。"
            return result
        image = self._scroll_to_top(image)

        at_top = True
        for _page in range(self.max_pages):
            page, failed = self._read_page(image)
            base = self._page_base(result, page, at_top) if page else len(result.rows) + 1
            for _ in range(self.retries):
                # 與已讀名次之間沒有缺號才合併；在最上面時第一列必須是第 1 名
                if base is not None and (base == 1 if at_top else base <= len(result.rows) + 1):
                    break
                if at_top:
                    break
                image = self._drag(DRAG_TO, DRAG_TO + DRAG_BACK)  # 可能滑過頭：往回拖再讀
                page, failed = self._read_page(image)
                base = self._page_base(result, page, at_top) if page else len(result.rows) + 1
            if base is None or (base != 1 if at_top else base > len(result.rows) + 1):
                if at_top:
                    result.stop_reason = f"名單最上面的名次是第 {base} 名，不是第 1 名，已停止。請確認名單已滑到最上面。"
                else:
                    result.stop_reason = (
                        f"已讀到第 {len(result.rows)} 名，但下一頁從第 {base} 名開始，中間有缺號；"
                        "為避免漏掉已停止，已讀部分存在本機。"
                        if base is not None
                        else "滑動後找不到與上一頁重疊的列，為避免名次錯位已停止，已讀部分存在本機。"
                    )
                return result
            self._append(result, page, base)
            if failed:
                result.stop_reason = f"第 {len(result.rows) + 1} 名的傷害或挑戰次數讀不出來，已停止，已讀部分存在本機。"
                return result
            at_top = False
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
