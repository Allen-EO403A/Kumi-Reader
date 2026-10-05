"""離線測試用的假遊戲：模擬成員列表、個人視窗與滑動，實作 Device 介面。"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

import members_flow as F

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
            self.mode = "info"
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


def make_rows(n: int, start: int = 0) -> list[Row]:
    return [
        Row(name=f"成員{i}", contribution=str(9000 - i), role="精英" if i % 2 else "豪傑", uid=f"{200000000000 + i}")
        for i in range(start, start + n)
    ]
