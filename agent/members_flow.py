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

"""程式 A：讀取家族成員（decisions.md 第 19 節「程式 A 流程」）。

流程：在「成員」分頁找出畫面上完整露出的每一列 → 從列表讀職位 → 點頭像開個人視窗
→ 點「個人資訊」分頁 → 讀暱稱與 ID → 點 X 關閉 → 這一頁做完就往上滑 → 滑動後畫面不變代表到底。
每一步先確認畫面；畫面不符時重試，仍不符就停下，已讀部分存在本機（之後補讀或上傳）。
補讀時傳入先前的進度，同樣從最上面滑到底，只開還沒讀過的列。
座標為 1920×1080 原始解析度，取自實機截圖（2026-10-03、10-04）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from kumi_reader import log
from kumi_reader.device import Device, Roi, StopRequested, region_changed
from kumi_reader.text import parse_int, parse_member_count, parse_name, parse_role
from kumi_reader.uid_digits import read_uid

# ---- 成員列表 ----
MEMBER_COUNT_ROI: Roi = (130, 762, 240, 52)  # 「成員：99/100」
LIST_TOP, LIST_BOTTOM = 287, 1009  # 列表可視範圍（表頭下緣～面板下緣）
# 用來找分隔線的空白欄：角色圖示與「最近上線」之間、面板右緣。兩欄都要符合才算分隔線。
# 不用暱稱右邊的空白：長暱稱（例如「墨染星夜離幽夢 (夜空)」）會延伸到 x≈1040，
# 文字邊緣的顏色被誤認成分隔線，整列被切壞而跳過（2026-10-05 實機）。
SEPARATOR_BANDS = ((1590, 1630), (1790, 1835))
ROW_HEIGHT = 113


def row_name_roi(top: int) -> Roi:
    return (685, top + 3, 320, 54)


def row_role_roi(top: int) -> Roi:
    return (685, top + 55, 120, 52)


def row_contribution_roi(top: int) -> Roi:
    return (1200, top + 30, 130, 54)


def row_avatar(top: int) -> tuple[int, int]:
    return (615, top + 57)


# ---- 個人視窗 ----
PROFILE_TAB = (265, 132)  # 「個人資訊」分頁
PROFILE_TAB_ROI: Roi = (215, 105, 170, 55)
PROFILE_CLOSE = (1748, 133)  # 右上角 X
PROFILE_NAME_ROI: Roi = (1145, 222, 312, 66)
PROFILE_ID_ROI: Roi = (1145, 296, 330, 46)

# ---- 滑動 ----
# 拖曳後停住再放開（沒有慣性）：拖 450 px 約移動 400 px ≈ 3.5 列，畫面 6 列，前後一定有重疊
DRAG_X = 1150
DRAG_FROM, DRAG_TO = 950, 500
DRAG_BACK = 170  # 沒有重疊時往回拖的距離（約 1.5 列）
TOP_FROM, TOP_TO = 420, 980  # 回到名單最上面
SETTLE_SECONDS = 0.6
LIST_REGION: Roi = (510, LIST_TOP, 1330, LIST_BOTTOM - LIST_TOP)


SEPARATOR_RGB = (205, 201, 170)  # 分隔線顏色（兩次實機截圖量到 203～205、199～201、169～176）
SEPARATOR_TOLERANCE = 14


def find_row_tops(image: np.ndarray) -> list[int]:
    """找出完整露出的列：回傳每列上緣的 y。

    以「顏色接近分隔線」判斷分隔線（列背景亮度會變，自己那一列是藍底，都不能用單一門檻）。
    名單在最上面時第一列上方沒有分隔線、在最下面時最後一列下方可能沒有，
    所以頭尾各多推一列當候選；呼叫端要再確認該列有內容（貢獻度讀得到數字）。
    """
    near = np.ones(LIST_BOTTOM - LIST_TOP, dtype=bool)
    for x0, x1 in SEPARATOR_BANDS:
        band = image[LIST_TOP:LIST_BOTTOM, x0:x1].astype(float).mean(axis=1)[:, ::-1]  # BGR → RGB
        near &= np.abs(band - np.array(SEPARATOR_RGB)).max(axis=1) <= SEPARATOR_TOLERANCE
    lines: list[int] = []
    for offset in np.flatnonzero(near):
        y = LIST_TOP + int(offset)
        if not lines or y - lines[-1] > 20:
            lines.append(y)
    tops = [a for a, b in zip(lines, lines[1:]) if 90 <= b - a <= 140]
    if lines and lines[0] - ROW_HEIGHT >= LIST_TOP - 4:
        tops.insert(0, lines[0] - ROW_HEIGHT)
    if lines and lines[-1] + ROW_HEIGHT <= LIST_BOTTOM + 2 and (not tops or tops[-1] != lines[-1]):
        tops.append(lines[-1])
    return tops


@dataclass
class MembersResult:
    expected: int | None = None
    members: dict[str, dict] = field(default_factory=dict)  # uid → {uid, name, role}
    failed_rows: int = 0
    complete: bool = False
    stop_reason: str | None = None
    stopped: bool = False  # 使用者按了停止


class MembersReader:
    """done_keys／known：先前讀過的列與成員（接續同一批次時略過，不再開個人視窗）。
    on_progress：每讀完一列呼叫一次，讓呼叫端存檔（中途停止也不會白讀）。"""

    def __init__(
        self,
        device: Device,
        max_pages: int = 60,
        retries: int = 3,
        done_keys: set[tuple[str, str]] | None = None,
        known: dict[str, dict] | None = None,
        on_progress=None,
        expected_override: int | None = None,
        extra_passes: int = 2,
    ):
        self.d = device
        self.max_pages = max_pages
        self.retries = retries
        self.done_keys = set(done_keys or ())
        self.known = dict(known or {})
        self.on_progress = on_progress or (lambda result, done: None)
        self.last_image: np.ndarray | None = None  # 停止時的畫面（除錯用）
        self.last_uid: str | None = None  # 上一位讀到的 UID（判斷個人視窗是否已換成下一個人）
        self.expected_override = expected_override  # 管理員自行輸入的成員數
        self.extra_passes = extra_passes  # 到底仍少人時，回到最上面再找的次數

    # -- 畫面確認 --
    def _on_list(self, image: np.ndarray) -> bool:
        return parse_member_count(self.d.ocr(image, MEMBER_COUNT_ROI)) is not None

    def _wait(self, check, seconds: float = 0.6, tries: int | None = None) -> np.ndarray | None:
        for _ in range(tries or self.retries + 2):
            self.d.sleep(seconds)
            image = self.d.screencap()
            self.last_image = image
            if check(image):
                return image
        return None

    def _profile_open(self, image: np.ndarray) -> bool:
        return "個人" in self.d.ocr(image, PROFILE_TAB_ROI)

    def _back_to_list(self) -> np.ndarray | None:
        """關閉個人視窗後回到列表；若視窗還開著（關閉沒點到），再點一次 X。"""
        for _ in range(self.retries):
            image = self._wait(self._on_list, seconds=0.9, tries=5)
            if image is not None:
                return image
            if self.last_image is not None and self._profile_open(self.last_image):
                self.d.click(*PROFILE_CLOSE)  # 視窗還開著時，這個位置是視窗的 X，點了是安全的
        return None

    # -- 主流程 --
    def run(self) -> MembersResult:
        result = MembersResult()
        try:
            return self._run(result)
        except StopRequested:
            result.complete = False
            result.stopped = True
            result.stop_reason = "已依要求停止。"
            return result

    def _run(self, result: MembersResult) -> MembersResult:
        image = self.d.screencap()
        count = parse_member_count(self.d.ocr(image, MEMBER_COUNT_ROI))
        if count is None:
            result.stop_reason = "目前不在家族面板的「成員」分頁。請打開「成員」分頁後再執行。"
            return result
        result.expected = self._expected(count[0])
        image = self._scroll_to_top(image)

        done_rows: set[tuple] = set(self.done_keys)
        result.members.update(self.known)
        passes_left = self.extra_passes
        pages = 0
        while pages < self.max_pages:
            pages += 1
            page_keys = self._page_keys(image)
            for top, key in page_keys:
                if key in done_rows:
                    continue  # 滑動後重複出現的列
                role = parse_role(self.d.ocr(image, row_role_roi(top)))
                member = self._read_profile(top)
                if member is None:
                    result.failed_rows += 1  # 不記為已處理：補讀時會再試這一列
                else:
                    member["role"] = role
                    result.members.setdefault(member["uid"], member)
                    log.info(f"已讀 {len(result.members)} / {result.expected} 人：{member['name'] or '（讀不出暱稱）'}")
                    done_rows.add(key)
                self.on_progress(result, done_rows)
                image = self._back_to_list()
                if image is None:
                    result.stop_reason = "關閉個人視窗後沒有回到成員列表，已停止。"
                    return result
                if result.expected and len(result.members) >= result.expected:
                    result.complete = True
                    return result

            before = image
            image = self._drag(DRAG_FROM, DRAG_TO)
            if not region_changed(before, image, LIST_REGION):
                # 已到底：人數相符才算讀完，否則提示缺幾人
                missing = (result.expected or 0) - len(result.members)
                result.complete = missing <= 0
                if not result.complete and passes_left > 0:
                    # 名單順序會隨上線狀態變動，讀取途中有人換位置就可能被跳過：
                    # 回到最上面再找一次，只開還沒讀過的列
                    passes_left -= 1
                    log.info(f"已到名單底部，還少 {missing} 人。名單順序可能在讀取中變動，從最上面再找一次…")
                    image = self._scroll_to_top(image)
                    pages = 0
                    continue
                if not result.complete:
                    result.stop_reason = (
                        f"已到名單底部，但只讀到 {len(result.members)} / {result.expected} 人，少 {missing} 人。"
                    )
                return result
            # 新畫面必須與上一頁有重疊的列，否則可能滑過頭漏讀：往回拖再確認
            previous = {key for _, key in page_keys}
            for _ in range(self.retries):
                if previous & {key for _, key in self._page_keys(image)}:
                    break
                image = self._drag(DRAG_TO, DRAG_TO + DRAG_BACK)
            else:
                result.stop_reason = "滑動後找不到與上一頁重疊的列，為避免漏讀已停止。"
                return result
        result.stop_reason = "讀取頁數超過上限，已停止。"
        return result

    def _expected(self, on_screen: int) -> int:
        """應讀人數：有輸入就用輸入值（與畫面上的數字不同時提醒），否則用畫面上的「成員：N/100」。"""
        if self.expected_override is None:
            return on_screen
        if self.expected_override != on_screen:
            log.warn(f"輸入的成員數 {self.expected_override} 與畫面上的 {on_screen} 不同，以輸入的數字核對。")
        return self.expected_override

    def _scroll_to_top(self, image: np.ndarray) -> np.ndarray:
        """名單可能停在中間或底部：一直往上拖到畫面不再改變。"""
        for _ in range(self.max_pages):
            after = self._drag(TOP_FROM, TOP_TO)
            if not region_changed(image, after, LIST_REGION):
                return after
            image = after
        return image

    def _drag(self, y1: int, y2: int) -> np.ndarray:
        self.d.drag(DRAG_X, y1, y2)
        self.d.sleep(SETTLE_SECONDS)
        return self.d.screencap()

    def _page_keys(self, image: np.ndarray) -> list[tuple[int, tuple[str, str]]]:
        """畫面上每一列的（上緣 y,（暱稱原文, 貢獻度原文））；略過沒有內容的候選位置。"""
        keys = []
        for top in find_row_tops(image):
            contribution = self.d.ocr(image, row_contribution_roi(top))
            if parse_int(contribution) is None:
                continue
            keys.append((top, (self.d.ocr(image, row_name_roi(top)), contribution)))
        return keys

    def _read_profile(self, top: int) -> dict | None:
        """點頭像 → 個人資訊 → 讀暱稱與 ID → 關閉。讀不出 UID 時回傳 None（這一列記為失敗）。

        UID 用數字字卡讀（uid_digits），連續兩張截圖讀到相同的 UID 才採用，避免截到畫面切換中途
        的圖；讀到和上一位相同的 UID 時，當作視窗還沒換成這個人，繼續等。"""
        self.d.click(*row_avatar(top))
        if self._wait(self._profile_open, seconds=0.7) is None:
            return None  # 沒開成個人視窗：不點任何其他地方，回列表繼續
        self.d.click(*PROFILE_TAB)
        member = None
        previous = None
        for _ in range(self.retries + 2):
            self.d.sleep(0.6)
            image = self.d.screencap()
            uid = read_uid(image)
            if uid is not None and uid == self.last_uid:
                uid = None
            if uid is not None and uid == previous:
                member = {"uid": uid, "name": parse_name(self.d.ocr(image, PROFILE_NAME_ROI))}
                self.last_uid = uid
                break
            previous = uid
        if member is None:
            log.warn("這一列的 UID 沒有連續兩次讀到相同的結果，先略過，之後補讀時會再試。")
        self.d.click(*PROFILE_CLOSE)
        return member


def build_upload(result: MembersResult, batch_id: int | None) -> dict:
    body: dict = {
        "status": "complete" if result.complete else "incomplete",
        "expectedCount": result.expected or 0,
        "members": list(result.members.values()),
    }
    if batch_id is not None:
        body["batchId"] = batch_id
    return body
