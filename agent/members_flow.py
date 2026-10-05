"""程式 A：讀取家族成員（decisions.md 第 19 節「程式 A 流程」）。

流程：在「成員」分頁找出畫面上完整露出的每一列 → 從列表讀職位 → 點頭像開個人視窗
→ 點「個人資訊」分頁 → 讀暱稱與 ID → 點 X 關閉 → 這一頁做完就往上滑 → 滑動後畫面不變代表到底。
每一步先確認畫面；畫面不符時重試，仍不符就停下並上傳已讀部分（批次標為未完成）。
座標為 1920×1080 原始解析度，取自實機截圖（2026-10-03、10-04）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from kumi_reader import log
from kumi_reader.device import Device, Roi, region_changed
from kumi_reader.text import parse_int, parse_member_count, parse_name, parse_role, parse_uid

# ---- 成員列表 ----
MEMBER_COUNT_ROI: Roi = (130, 762, 240, 52)  # 「成員：99/100」
LIST_TOP, LIST_BOTTOM = 287, 1009  # 列表可視範圍（表頭下緣～面板下緣）
SEPARATOR_X = (1000, 1150)  # 用來找分隔線的空白欄
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
SWIPE_FROM = (1150, 950)
SWIPE_TO = (1150, 420)
SWIPE_MS = 900
SETTLE_SECONDS = 1.0
LIST_REGION: Roi = (510, LIST_TOP, 1330, LIST_BOTTOM - LIST_TOP)


SEPARATOR_RGB = (205, 201, 170)  # 分隔線顏色（兩次實機截圖量到 203～205、199～201、169～176）
SEPARATOR_TOLERANCE = 14


def find_row_tops(image: np.ndarray) -> list[int]:
    """找出完整露出的列：回傳每列上緣的 y。

    以「顏色接近分隔線」判斷分隔線（列背景亮度會變，自己那一列是藍底，都不能用單一門檻）。
    名單在最上面時第一列上方沒有分隔線、在最下面時最後一列下方可能沒有，
    所以頭尾各多推一列當候選；呼叫端要再確認該列有內容（貢獻度讀得到數字）。
    """
    x0, x1 = SEPARATOR_X
    band = image[LIST_TOP:LIST_BOTTOM, x0:x1].astype(float).mean(axis=1)[:, ::-1]  # BGR → RGB
    near = np.abs(band - np.array(SEPARATOR_RGB)).max(axis=1) <= SEPARATOR_TOLERANCE
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


class MembersReader:
    def __init__(self, device: Device, max_pages: int = 60, retries: int = 3):
        self.d = device
        self.max_pages = max_pages
        self.retries = retries

    # -- 畫面確認 --
    def _on_list(self, image: np.ndarray) -> bool:
        return parse_member_count(self.d.ocr(image, MEMBER_COUNT_ROI)) is not None

    def _wait(self, check, seconds: float = 0.6) -> np.ndarray | None:
        for _ in range(self.retries + 2):
            self.d.sleep(seconds)
            image = self.d.screencap()
            if check(image):
                return image
        return None

    # -- 主流程 --
    def run(self) -> MembersResult:
        result = MembersResult()
        image = self.d.screencap()
        count = parse_member_count(self.d.ocr(image, MEMBER_COUNT_ROI))
        if count is None:
            result.stop_reason = "目前不在家族面板的「成員」分頁。請打開「成員」分頁後再執行。"
            return result
        result.expected = count[0]

        done_rows: set[tuple] = set()
        for _page in range(self.max_pages):
            for top in find_row_tops(image):
                contribution = self.d.ocr(image, row_contribution_roi(top))
                if parse_int(contribution) is None:
                    continue  # 不是成員列（頭尾推出來的候選位置沒有內容）
                key = (self.d.ocr(image, row_name_roi(top)), contribution)
                if key in done_rows:
                    continue  # 滑動後重複出現的列
                role = parse_role(self.d.ocr(image, row_role_roi(top)))
                member = self._read_profile(top)
                if member is None:
                    result.failed_rows += 1
                else:
                    member["role"] = role
                    result.members.setdefault(member["uid"], member)
                    log.info(f"已讀 {len(result.members)} / {result.expected} 人：{member['name'] or '（讀不出暱稱）'}")
                done_rows.add(key)
                image = self._wait(self._on_list)
                if image is None:
                    result.stop_reason = "關閉個人視窗後沒有回到成員列表，已停止。"
                    return result
                if result.expected and len(result.members) >= result.expected:
                    result.complete = True
                    return result

            before = image
            self.d.swipe(*SWIPE_FROM, *SWIPE_TO, SWIPE_MS)
            self.d.sleep(SETTLE_SECONDS)
            image = self.d.screencap()
            if not region_changed(before, image, LIST_REGION):
                result.complete = True  # 滑動後畫面不變：已到底
                return result
        result.stop_reason = "讀取頁數超過上限，已停止。"
        return result

    def _read_profile(self, top: int) -> dict | None:
        """點頭像 → 個人資訊 → 讀暱稱與 ID → 關閉。讀不出 UID 時回傳 None（這一列記為失敗）。"""
        self.d.click(*row_avatar(top))
        if self._wait(lambda img: "個人" in self.d.ocr(img, PROFILE_TAB_ROI)) is None:
            return None  # 沒開成個人視窗：不點任何其他地方，回列表繼續
        self.d.click(*PROFILE_TAB)
        member = None
        for _ in range(self.retries):
            self.d.sleep(0.5)
            image = self.d.screencap()
            uid = parse_uid(self.d.ocr(image, PROFILE_ID_ROI))
            if uid:
                member = {"uid": uid, "name": parse_name(self.d.ocr(image, PROFILE_NAME_ROI))}
                break
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
