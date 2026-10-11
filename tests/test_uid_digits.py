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

import numpy as np

from fake_game import draw_uid
from kumi_reader import uid_digits as U


def blank() -> np.ndarray:
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    image[:, :] = (127, 89, 70)  # 個人資訊頁的藍底（BGR）
    return image


def test_reads_every_digit():
    for uid in ("012345678901", "271406869019", "371606022030", "999999999999"):
        image = blank()
        draw_uid(image, uid)
        assert U.read_uid(image) == uid


def test_blank_or_partial_id_is_unreadable():
    assert U.read_uid(blank()) is None
    image = blank()
    draw_uid(image, "27140686901")  # 11 碼：最後一格空白
    assert U.read_uid(image) is None


def test_thirteen_digits_is_unreadable():
    image = blank()
    draw_uid(image, "2714068690191")
    assert U.read_uid(image) is None


def test_overlapping_screens_never_mix_digits():
    """切換中兩個人的畫面疊在一起：只能讀出其中一人或讀不出，不能拼出第三個 UID。"""
    a, b = blank(), blank()
    draw_uid(a, "271406869019")
    draw_uid(b, "371606022030")
    for t in (0.2, 0.35, 0.5, 0.65, 0.8):
        mixed = (a.astype(float) * t + b.astype(float) * (1 - t)).astype(np.uint8)
        assert U.read_uid(mixed) in (None, "271406869019", "371606022030")
