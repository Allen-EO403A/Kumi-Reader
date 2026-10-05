"""操作模擬器的介面：截圖、點擊、滑動、在固定區域 OCR。

讀取流程只透過 Device 操作，所以可以用截圖序列（FakeDevice）離線測試，
實機時由 MaaDevice 透過 MaaFramework 執行。座標一律為 1920×1080 原始解析度。
"""
from __future__ import annotations

import time
from typing import Protocol

import numpy as np

Roi = tuple[int, int, int, int]  # x, y, w, h


class Device(Protocol):
    def screencap(self) -> np.ndarray: ...
    def click(self, x: int, y: int) -> None: ...
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None: ...
    def drag(self, x: int, y1: int, y2: int) -> None: ...
    def ocr(self, image: np.ndarray, roi: Roi) -> str: ...
    def sleep(self, seconds: float) -> None: ...


def region_changed(a: np.ndarray, b: np.ndarray, roi: Roi, threshold: float = 4.0) -> bool:
    """兩張截圖在區域內的平均像素差是否超過門檻（用來判斷滾動後畫面是否改變）。"""
    x, y, w, h = roi
    diff = np.abs(a[y : y + h, x : x + w].astype(np.int16) - b[y : y + h, x : x + w].astype(np.int16))
    return float(diff.mean()) > threshold


class MaaDevice:
    """實機：透過 MaaFramework 的 Context 操作 MFAAvalonia 連上的模擬器。"""

    def __init__(self, context):
        from maa.pipeline import JOCR, JRecognitionType

        self._context = context
        self._controller = context.tasker.controller
        self._JOCR = JOCR
        self._OCR = JRecognitionType.OCR

    def screencap(self) -> np.ndarray:
        return self._controller.post_screencap().wait().get()

    def click(self, x: int, y: int) -> None:
        self._controller.post_click(x, y).wait()

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
        self._controller.post_swipe(x1, y1, x2, y2, duration_ms).wait()

    def drag(self, x: int, y1: int, y2: int, steps: int = 12, hold: float = 0.4) -> None:
        """按下 → 分段移動 → 停住再放開。停住可以消掉慣性，每次移動的距離才會固定
        （2026-10-05 實機：拖 340 px 實際移動 283～312 px，不會滑過頭）。"""
        self._controller.post_touch_down(x, y1).wait()
        for i in range(1, steps + 1):
            self._controller.post_touch_move(x, round(y1 + (y2 - y1) * i / steps)).wait()
            time.sleep(0.02)
        time.sleep(hold)
        self._controller.post_touch_up().wait()

    def ocr(self, image: np.ndarray, roi: Roi) -> str:
        # 只辨識、不偵測：固定區域內的文字（decisions.md 第 19 節）
        param = self._JOCR(roi=list(roi), only_rec=True, threshold=0.0)
        detail = self._context.run_recognition_direct(self._OCR, param, image)
        if not detail:
            return ""
        return "".join(r.text for r in detail.all_results)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
