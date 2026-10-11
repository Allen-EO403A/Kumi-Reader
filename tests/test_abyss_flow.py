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

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import abyss_flow as F
from fake_abyss import TOPS, FakeAbyss, make_entries

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "abyss-bottom.png"


@pytest.mark.skipif(not SAMPLE.exists(), reason="需要 samples/abyss-bottom.png（實機截圖，不提交）")
def test_real_screenshot_rows_and_tab():
    image = np.array(Image.open(SAMPLE).convert("RGB"))[:, :, ::-1].copy()
    # 最上面被切掉的列與底部黃色的自己都不算
    assert F.find_row_tops(image) == [196, 331, 466, 601, 736]
    assert F.on_family_tab(image, "傷害")


def test_reads_whole_list_in_order_from_the_top():
    entries = make_entries(13)
    game = FakeAbyss(entries, offset=8)  # 開始時停在名單中間
    result = F.AbyssReader(game).run()
    assert result.complete and result.stop_reason is None
    assert [r.rank for r in result.rows] == list(range(1, 14))
    assert [r.name for r in result.rows] == [e.name for e in entries]
    assert result.rows[0].role == "精英"
    assert result.rows[2].damage == 8_900_000
    assert game.clicks == []  # 程式 B 不點擊


def test_skips_a_repeated_row_even_if_its_name_reads_differently():
    entries = make_entries(9)
    # 第 5 名在第二頁重複出現時暱稱讀成別的字
    entries[4].second_look_name = "玩家五"
    result = F.AbyssReader(FakeAbyss(entries)).run()
    assert [r.rank for r in result.rows] == list(range(1, 10))
    assert len(result.rows) == 9


def test_stops_and_keeps_rows_when_a_number_is_unreadable():
    entries = make_entries(9)
    entries[6].unreadable_damage = True
    result = F.AbyssReader(FakeAbyss(entries)).run()
    assert not result.complete
    assert "第 7 名" in result.stop_reason
    assert len(result.rows) == 6
    body = F.build_upload(result, batch_id=3)
    assert body["status"] == "incomplete"
    assert body["lastRank"] == 6
    assert body["batchId"] == 3


def test_refuses_to_start_on_another_tab():
    game = FakeAbyss(make_entries(5), family_tab=False)
    result = F.AbyssReader(game).run()
    assert "家族狀況" in result.stop_reason
    assert result.rows == []


def test_build_upload_shape():
    result = F.AbyssResult(rows=[F.AbyssRow(1, "千夏", "族員", 2736399, 2), F.AbyssRow(2, None, None, 100, 1)], complete=True)
    assert F.build_upload(result, batch_id=None) == {
        "status": "complete",
        "lastRank": 2,
        "rows": [
            {"rank": 1, "name": "千夏", "role": "族員", "damage": 2736399, "challengeCount": 2},
            {"rank": 2, "name": None, "role": None, "damage": 100, "challengeCount": 1},
        ],
    }


def test_find_row_tops_on_synthetic_offsets():
    image = FakeAbyss(make_entries(5)).screencap()
    assert F.find_row_tops(image) == TOPS


def test_medal_ranks_at_top_are_inferred_from_the_rest_of_the_page():
    entries = make_entries(9)
    for e in entries[:3]:
        e.rank_text = ""  # 前三名是金銀銅圖示，讀不出數字
    result = F.AbyssReader(FakeAbyss(entries)).run()
    assert result.complete
    assert [r.rank for r in result.rows] == list(range(1, 10))
    assert result.rows[0].name == "玩家1"


def test_a_misread_rank_is_outvoted_by_the_rest_of_the_page():
    entries = make_entries(9)
    entries[6].rank_text = "1"  # 第 7 名讀成 1
    result = F.AbyssReader(FakeAbyss(entries)).run()
    assert [(r.rank, r.name) for r in result.rows] == [(i + 1, f"玩家{i + 1}") for i in range(9)]


def test_rows_with_identical_numbers_are_not_merged():
    # 傷害與挑戰次數完全相同的兩人：以名次合併，不會被當成同一列
    entries = make_entries(9)
    for e in entries[3:6]:
        e.damage, e.challenges = 5_000_000, 21
    result = F.AbyssReader(FakeAbyss(entries)).run()
    assert [r.rank for r in result.rows] == list(range(1, 10))
    assert [r.name for r in result.rows] == [e.name for e in entries]


def test_stops_when_a_gap_in_ranks_cannot_be_closed():
    entries = make_entries(20)
    game = FakeAbyss(entries, overshoot=3, drag_back_works=False)  # 每次多滑 3 列，往回拖也回不去
    result = F.AbyssReader(game).run()
    assert not result.complete
    assert "缺號" in result.stop_reason
    assert [r.rank for r in result.rows] == list(range(1, len(result.rows) + 1))


def test_first_row_under_the_header_is_found_at_top_of_list():
    # 名單在最上面：第 1 名上方是表頭，沒有深色分隔線
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    image[:, :] = (219, 193, 205)
    for y in [270, 405, 540, 675, 810]:
        image[y : y + 4, :] = (46, 28, 19)
    assert F.find_row_tops(image)[:2] == [135, 270]


TOP_SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "abyss-top.png"


@pytest.mark.skipif(not TOP_SAMPLE.exists(), reason="需要 samples/abyss-top.png（實機截圖，不提交）")
def test_real_screenshot_top_of_list_includes_first_place():
    image = np.array(Image.open(TOP_SAMPLE).convert("RGB"))[:, :, ::-1].copy()
    assert F.find_row_tops(image) == [135, 270, 405, 540, 675]
