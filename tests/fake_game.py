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

"""離線測試用的假遊戲：模擬成員列表、個人視窗與滑動，實作 Device 介面。"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

import members_flow as F
from kumi_reader import uid_digits as U

BG = (199, 217, 219)  # BGR，背景約 RGB(219,217,199)
LINE = (170, 199, 203)  # BGR，分隔線約 RGB(203,199,170)


@dataclass
class Row:
    name: str
    contribution: str
    role: str
    uid: str
    profile_name: str | None = None
    uid_readable: bool = True
    glitch_uid: str | None = None  # 開啟後前幾張截圖顯示的錯誤 UID（模擬畫面切換中途）
    glitch_shots: int = 1


@dataclass
class Page:
    tops: list[int]  # 每列上緣分隔線
    rows: list[Row]


@dataclass
class FakeGame:
    pages: list[Page]
    expected: int
    on_list_at_start: bool = True
    drag_back_works: bool = True
    page: int = 0
    mode: str = "list"  # list / dress（搭配分頁）/ info（個人資訊分頁）
    current: Row | None = None
    clicks: list[tuple[int, int]] = field(default_factory=list)
    drags: list[tuple[int, int]] = field(default_factory=list)
    snapshots: dict[int, tuple] = field(default_factory=dict)
    info_shots: int = 0  # 目前這個個人資訊頁已經截了幾張

    def screencap(self) -> np.ndarray:
        image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        image[:, :] = BG
        page = self.pages[self.page]
        mode = self.mode if self.on_list_at_start else "elsewhere"
        if mode == "list":
            for top in page.tops + [page.tops[-1] + F.ROW_HEIGHT]:
                image[top : top + 2, :] = LINE
            # 每一頁的內容不同（讓「滑動後畫面是否改變」可以判斷）
            # 實機滑動時整個列表都會變；用大塊區域模擬（避開找分隔線的空白欄）
            image[F.LIST_TOP : F.LIST_BOTTOM, 1200:1500] = (60 + self.page * 37) % 256
        if mode == "info" and self.current and self.current.uid_readable:
            self.info_shots += 1
            glitch = self.current.glitch_uid if self.info_shots <= self.current.glitch_shots else None
            draw_uid(image, glitch or self.current.uid)
        self.snapshots[id(image)] = (mode, self.page, self.current)
        return image

    def ocr(self, image: np.ndarray, roi) -> str:
        mode, page_no, current = self.snapshots[id(image)]
        page = self.pages[page_no]
        if mode == "list":
            if tuple(roi) == F.MEMBER_COUNT_ROI:
                return f"成員：{self.expected}/100"
            for top, row in zip(page.tops, page.rows):
                if tuple(roi) == F.row_name_roi(top):
                    return row.name
                if tuple(roi) == F.row_role_roi(top):
                    return row.role
                if tuple(roi) == F.row_contribution_roi(top):
                    return row.contribution
            return ""
        if mode in ("dress", "info") and tuple(roi) == F.PROFILE_TAB_ROI:
            return "個人資訊"
        if mode == "info" and current:
            if tuple(roi) == F.PROFILE_ID_ROI:
                return f"ID：{current.uid}" if current.uid_readable else "ID：????"
            if tuple(roi) == F.PROFILE_NAME_ROI:
                return current.profile_name or current.name
        return ""

    def click(self, x: int, y: int) -> None:
        self.clicks.append((x, y))
        if self.mode == "list":
            page = self.pages[self.page]
            for top, row in zip(page.tops, page.rows):
                if (x, y) == F.row_avatar(top):
                    self.mode, self.current = "dress", row
        elif (x, y) == F.PROFILE_TAB:
            self.mode, self.info_shots = "info", 0
        elif (x, y) == F.PROFILE_CLOSE:
            self.mode, self.current = "list", None

    def swipe(self, x1, y1, x2, y2, duration_ms) -> None:
        raise AssertionError("程式 A 應該用 drag（停住再放開），不用會有慣性的 swipe")

    def drag(self, x, y1, y2) -> None:
        self.drags.append((y1, y2))
        if y2 < y1:
            self.page = min(self.page + 1, len(self.pages) - 1)
        elif self.drag_back_works:
            self.page = max(self.page - 1, 0)

    def sleep(self, seconds: float) -> None:
        pass


def draw_uid(image: np.ndarray, uid: str) -> None:
    """以字卡把 UID 畫在個人資訊頁的位置（底色與字色同實機）。"""
    templates = U.load_templates()
    low, high = np.array((127, 89, 70)), np.array((203, 173, 165))  # BGR
    image[U.DIGITS_Y - 10 : U.DIGITS_Y + U.CELL_H + 10, U.DIGITS_X - 10 : U.cell_x(14)] = low
    for i, digit in enumerate(uid):
        x = U.cell_x(i)
        strength = templates[digit][..., None]
        image[U.DIGITS_Y : U.DIGITS_Y + U.CELL_H, x : x + U.CELL_W] = np.round(low + (high - low) * strength)


def make_rows(n: int, start: int = 0) -> list[Row]:
    return [
        Row(name=f"成員{i}", contribution=str(9000 - i), role="精英" if i % 2 else "豪傑", uid=f"{200000000000 + i}")
        for i in range(start, start + n)
    ]
