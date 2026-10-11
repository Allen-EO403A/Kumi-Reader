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

"""以數字字卡讀個人資訊頁的 UID，不用 OCR。

OCR 會把 UID 讀錯（2026-10-11 實機：271406869019 讀成 371406860012 等），讀錯的 UID
又剛好是 12 碼，無法從格式發現。個人資訊頁「ID：」後面的數字是固定字型、固定位置的
等寬字（每格約 19.09 px），所以切成 12 格，每格與 0～9 的字卡比對（正規化相關係數，
上下左右各容許 2 px 偏移）。有任何一格不夠像、或與次像的數字差距不夠大，就當作讀不出來，
不猜。字卡 `uid_digits.png` 由 `tools/build_uid_digits.py` 從實機截圖產生。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

# 第一碼左緣、字距、每格寬高（1920×1080 原始解析度，2026-10-03 實機截圖量測）
DIGITS_X = 1220
DIGITS_PITCH = 19.09
CELL_W, CELL_H = 18, 28
DIGITS_Y = 305
UID_LENGTH = 12
SHIFT = 2  # 比對時容許的偏移

# 底色約 RGB(70,89,127)、字約 RGB(165,173,203)：取三色最小值，底 ≈ 70、字 ≈ 165
INK_LOW, INK_HIGH = 70, 165

MIN_SCORE = 0.88  # 實機截圖中正確數字最低 0.95
MIN_MARGIN = 0.08  # 與次像的數字至少差這麼多（實機最像的錯誤數字最高 0.74）

TEMPLATE_PATH = Path(__file__).with_name("uid_digits.png")


def ink(image: np.ndarray) -> np.ndarray:
    """淺色字的濃度 0～1（底色為 0）。"""
    lowest = image.min(axis=2).astype(np.float32)
    return np.clip((lowest - INK_LOW) / (INK_HIGH - INK_LOW), 0.0, 1.0)


def cell_x(index: int) -> int:
    return round(DIGITS_X + index * DIGITS_PITCH)


def cut_cells(image: np.ndarray, count: int = UID_LENGTH, pad: int = SHIFT) -> list[np.ndarray]:
    """切出每一格（含比對偏移用的邊界）。"""
    strength = ink(image)
    return [
        strength[DIGITS_Y - pad : DIGITS_Y + CELL_H + pad, cell_x(i) - pad : cell_x(i) + CELL_W + pad]
        for i in range(count)
    ]


def load_templates(path: Path = TEMPLATE_PATH) -> dict[str, np.ndarray]:
    strip = np.asarray(Image.open(path).convert("L"), dtype=np.float32) / 255.0
    return {str(d): strip[:, d * CELL_W : (d + 1) * CELL_W] for d in range(10)}


def _ncc(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    denominator = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum()) / denominator if denominator else 0.0


def match(cell: np.ndarray, template: np.ndarray) -> float:
    best = -1.0
    for dy in range(2 * SHIFT + 1):
        for dx in range(2 * SHIFT + 1):
            best = max(best, _ncc(cell[dy : dy + CELL_H, dx : dx + CELL_W], template))
    return best


_templates: dict[str, np.ndarray] | None = None


def read_uid(image: np.ndarray) -> str | None:
    """讀出 12 碼 UID；任何一格沒把握，或第 13 格有字（不是 12 碼）時回傳 None。"""
    global _templates
    if _templates is None:
        _templates = load_templates()
    after = ink(image)[DIGITS_Y : DIGITS_Y + CELL_H, cell_x(UID_LENGTH) : cell_x(UID_LENGTH) + CELL_W]
    if after.max() > 0.5:
        return None
    digits = []
    for cell in cut_cells(image):
        scores = sorted(((match(cell, t), d) for d, t in _templates.items()), reverse=True)
        (best, digit), (second, _) = scores[0], scores[1]
        if best < MIN_SCORE or best - second < MIN_MARGIN:
            return None
        digits.append(digit)
    return "".join(digits)
