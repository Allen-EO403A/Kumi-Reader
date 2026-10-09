# Kumi Reader - 讀取「忍者必須死3」家族成員與深淵排行並上傳到 Kumi
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

"""離線測試用的假遊戲：模擬深淵排行「家族狀況」分頁的滑動，實作 Device 介面。"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

import abyss_flow as F

BG = (219, 193, 205)  # BGR，列背景約 RGB(205,193,219)
LINE = (46, 28, 19)  # BGR，分隔線約 RGB(19,28,46)
TAB_SELECTED = (207, 183, 195)
TAB_OTHER = (175, 113, 143)
TOPS = [196, 331, 466, 601, 736]  # 實機截圖量到的分隔線（每頁 5 列）


@dataclass
class Entry:
    name: str
    role: str
    damage: int
    challenges: int
    unreadable_damage: bool = False
    second_look_name: str | None = None  # 第二次出現時 OCR 讀到的暱稱（模擬讀取不一致）
    rank_text: str | None = None  # 名次 OCR 的結果；None 時為正確名次（"" 模擬金銀銅圖示讀不出）


@dataclass
class FakeAbyss:
    entries: list[Entry]
    offset: int = 0
    family_tab: bool = True
    overshoot: int = 0  # 每次拖動多滑的列數（模擬滑過頭）
    drag_back_works: bool = True
    clicks: list[tuple[int, int]] = field(default_factory=list)
    snapshots: dict[int, int] = field(default_factory=dict)
    seen_offsets: set[int] = field(default_factory=set)

    @property
    def max_offset(self) -> int:
        return max(0, len(self.entries) - len(TOPS))

    def screencap(self) -> np.ndarray:
        image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        image[:, :] = BG
        image[40:60, 880:920] = TAB_SELECTED if self.family_tab else TAB_OTHER
        for top in TOPS + [TOPS[-1] + F.ROW_HEIGHT]:
            image[top : top + 4, :] = LINE
        # 不同位置的內容不同（避開找分隔線的空白欄）
        image[F.LIST_TOP : F.LIST_BOTTOM, 1200:1600] = (30 + self.offset * 29) % 256
        self.snapshots[id(image)] = self.offset
        return image

    def ocr(self, image: np.ndarray, roi) -> str:
        offset = self.snapshots[id(image)]
        roi = tuple(roi)
        if roi == F.HEADER_ROI:
            return "傷害"
        for i, top in enumerate(TOPS):
            index = offset + i
            if index >= len(self.entries):
                break
            e = self.entries[index]
            if roi == F.row_name_roi(top):
                again = index in self.seen_offsets and e.second_look_name
                self.seen_offsets.add(index)
                return e.second_look_name if again else e.name
            if roi == F.row_role_roi(top):
                return e.role
            if roi == F.row_rank_roi(top):
                return str(index + 1) if e.rank_text is None else e.rank_text
            if roi == F.row_damage_roi(top):
                return "??" if e.unreadable_damage else str(e.damage)
            if roi == F.row_challenges_roi(top):
                return str(e.challenges)
        return ""

    def click(self, x: int, y: int) -> None:
        self.clicks.append((x, y))

    def swipe(self, x1, y1, x2, y2, duration_ms) -> None:
        raise AssertionError("程式 B 應該用 drag（停住再放開），不用會有慣性的 swipe")

    def drag(self, x, y1, y2) -> None:
        # 停住再放開：實際移動約為拖動距離的九成
        rows = max(1, round(abs(y2 - y1) * 0.9 / F.ROW_HEIGHT)) + self.overshoot
        if y2 < y1:  # 手指往上：看後面的名次
            self.offset = min(self.offset + rows, self.max_offset)
        elif self.drag_back_works:
            self.offset = max(self.offset - rows, 0)

    def sleep(self, seconds: float) -> None:
        pass


def make_entries(n: int) -> list[Entry]:
    roles = ["精英", "豪傑", "族員", "長老"]
    return [Entry(f"玩家{i + 1}", roles[i % 4], 9_000_000 - i * 50_000, 20 - i % 5) for i in range(n)]
